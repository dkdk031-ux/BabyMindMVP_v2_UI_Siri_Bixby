import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const typeNames = {
  'formula': '분유',
  'breastfeed': '모유',
  'sleep': '수면',
  'diaper': '기저귀',
  'meal': '식사',
  'medicine': '약',
  'temperature': '체온',
  'memo': '메모',
};
const typeIcons = {
  'formula': '🍼',
  'breastfeed': '🤱',
  'sleep': '😴',
  'diaper': '🧷',
  'meal': '🍚',
  'medicine': '💊',
  'temperature': '🌡️',
  'memo': '📝',
};

class BabyEvent {
  final int id;
  final String type;
  final DateTime startedAt;
  final DateTime? endedAt;
  final double? amount;
  final String? unit;
  final String? note;
  final String source;

  BabyEvent.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        type = j['type'],
        startedAt = DateTime.parse(j['started_at']).toLocal(),
        endedAt = j['ended_at'] == null ? null : DateTime.parse(j['ended_at']).toLocal(),
        amount = (j['amount'] as num?)?.toDouble(),
        unit = j['unit'],
        note = j['note'],
        source = j['source'] ?? 'app';

  String get icon => typeIcons[type] ?? '📝';

  String get label {
    var s = typeNames[type] ?? type;
    final a = amount;
    if (a != null) s += ' ${a == a.roundToDouble() ? a.toInt() : a}${unit ?? ''}';
    final end = endedAt;
    if (end != null) {
      final m = end.difference(startedAt).inMinutes;
      s += m >= 60 ? ' · ${m ~/ 60}시간 ${m % 60}분' : ' · $m분';
    }
    return s;
  }
}

class Summary {
  final double formulaMl;
  final int formulaCount, sleepMin, diaperCount;
  final DateTime? lastFormulaAt;

  Summary.fromJson(Map<String, dynamic> j)
      : formulaMl = (j['formula_ml'] as num).toDouble(),
        formulaCount = j['formula_count'],
        sleepMin = j['sleep_min'],
        diaperCount = j['diaper_count'],
        lastFormulaAt = j['last_formula_at'] == null ? null : DateTime.parse(j['last_formula_at']).toLocal();
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

class Api {
  static const _urlKey = 'server_url', _tokenKey = 'server_token';
  String baseUrl = '';
  String token = '';

  bool get configured => baseUrl.isNotEmpty;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    baseUrl = p.getString(_urlKey) ?? '';
    token = p.getString(_tokenKey) ?? '';
  }

  Future<void> save(String url, String tok) async {
    var u = url.trim();
    if (u.isNotEmpty && !u.startsWith('http')) u = 'http://$u';
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    baseUrl = u;
    token = tok.trim();
    final p = await SharedPreferences.getInstance();
    await p.setString(_urlKey, baseUrl);
    await p.setString(_tokenKey, token);
  }

  Map<String, String> get _headers =>
      {'Content-Type': 'application/json', if (token.isNotEmpty) 'X-API-Key': token};

  Future<dynamic> _send(String method, String path, [Object? body]) async {
    if (!configured) throw ApiException('설정에서 서버 주소를 입력해 주세요.');
    final uri = Uri.parse('$baseUrl$path');
    final req = http.Request(method, uri)..headers.addAll(_headers);
    if (body != null) req.body = jsonEncode(body);
    try {
      final res = await http.Response.fromStream(await req.send().timeout(const Duration(seconds: 20)));
      final text = utf8.decode(res.bodyBytes);
      if (res.statusCode >= 300) {
        String msg = text;
        try {
          msg = jsonDecode(text)['detail'].toString();
        } catch (_) {}
        throw ApiException('서버 오류(${res.statusCode}): $msg');
      }
      return jsonDecode(text);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('서버에 연결할 수 없어요. 주소와 Wi-Fi를 확인해 주세요.\n($e)');
    }
  }

  /// 같은 Wi-Fi 안에서 BabyMind 서버를 찾아 주소와 인증 키를 자동 저장. 찾으면 true.
  Future<bool> discover({int port = 8000}) async {
    final prefixes = <String>{};
    // PC 브라우저에서 열었으면 앱 화면을 준 서버가 곧 BabyMind 서버
    final webOrigin = kIsWeb ? Uri.base.origin : null;
    for (final nic in kIsWeb ? <NetworkInterface>[] : await NetworkInterface.list(type: InternetAddressType.IPv4)) {
      for (final a in nic.addresses) {
        final p = a.address.split('.');
        final first = int.parse(p[0]), second = int.parse(p[1]);
        final private = first == 10 || (first == 192 && second == 168) || (first == 172 && second >= 16 && second <= 31);
        if (private) prefixes.add('${p[0]}.${p[1]}.${p[2]}');
      }
    }
    // 이전에 쓰던 주소가 있으면 먼저 확인
    final candidates = <String>[
      ?webOrigin,
      if (baseUrl.isNotEmpty && baseUrl != webOrigin) baseUrl,
      for (final pre in prefixes) for (var i = 1; i < 255; i++) 'http://$pre.$i:$port',
    ];
    final found = Completer<Map<String, String>?>();
    var pending = candidates.length;
    final client = http.Client();
    for (final url in candidates) {
      client.get(Uri.parse('$url/pair')).timeout(const Duration(seconds: 2)).then((res) {
        final j = jsonDecode(utf8.decode(res.bodyBytes));
        if (j is Map && j['app'] == 'babymind' && !found.isCompleted) {
          found.complete({'url': url, 'token': '${j['token'] ?? ''}'});
        }
      }).catchError((_) {}).whenComplete(() {
        if (--pending == 0 && !found.isCompleted) found.complete(null);
      });
    }
    if (candidates.isEmpty) return false;
    final r = await found.future;
    client.close();
    if (r == null) return false;
    await save(r['url']!, r['token']!);
    return true;
  }

  Future<String> health() async => (await _send('GET', '/health')).toString();

  /// 문장 한 줄을 서버에서 해석해 저장. 스피커가 읽을 문장(speech)을 돌려준다.
  Future<String> log(String text) async =>
      (await _send('POST', '/log', {'text': text, 'source': 'app'}))['speech'];

  Future<List<BabyEvent>> events({int days = 1}) async {
    final list = await _send('GET', '/events?days=$days') as List;
    return list.map((e) => BabyEvent.fromJson(e)).toList();
  }

  Future<Summary> summary() async => Summary.fromJson(await _send('GET', '/summary'));

  Future<void> delete(int id) => _send('DELETE', '/events/$id');

  Future<String> ask(String q) async => (await _send('POST', '/ask', {'question': q}))['answer'];
}
