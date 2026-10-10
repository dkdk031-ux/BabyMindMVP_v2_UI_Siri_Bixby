import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'api.dart';

void main() => runApp(const BabyMindApp());

class BabyMindApp extends StatelessWidget {
  const BabyMindApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'BabyMind',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  final api = Api();
  final stt = SpeechToText();
  final input = TextEditingController();
  final question = TextEditingController();
  Timer? poller;

  int tab = 0;
  bool busy = false, listening = false, sttReady = false;
  String status = '말하거나 입력해 주세요';
  String transcript = '';
  String answer = '';
  List<BabyEvent> events = [];
  Summary? summary;

  List<BabyEvent> get today {
    final now = DateTime.now();
    return events
        .where((e) => e.startedAt.year == now.year && e.startedAt.month == now.month && e.startedAt.day == now.day)
        .toList();
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _start();
  }

  Future<void> _start() async {
    await api.load();
    if (!api.configured) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _openSettings());
    }
    await refresh();
    _startPolling();
  }

  // 스피커(Bixby)로 들어온 기록이 앱에 바로 보이도록 화면이 켜져 있는 동안 주기적으로 새로고침
  void _startPolling() {
    poller?.cancel();
    poller = Timer.periodic(const Duration(seconds: 15), (_) => refresh(quiet: true));
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      refresh(quiet: true);
      _startPolling();
    } else if (state == AppLifecycleState.paused) {
      poller?.cancel();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poller?.cancel();
    input.dispose();
    question.dispose();
    super.dispose();
  }

  Future<void> refresh({bool quiet = false}) async {
    if (!api.configured) return;
    try {
      final r = await Future.wait([api.events(days: 7), api.summary()]);
      if (!mounted) return;
      setState(() {
        events = r[0] as List<BabyEvent>;
        summary = r[1] as Summary;
      });
    } catch (e) {
      if (!quiet && mounted) setState(() => status = e.toString());
    }
  }

  Future<void> submit(String text) async {
    if (text.trim().isEmpty || busy) return;
    setState(() {
      busy = true;
      status = '기록 중…';
    });
    try {
      final speech = await api.log(text);
      input.clear();
      setState(() => status = '✓ $speech');
      await refresh();
    } catch (e) {
      setState(() => status = '오류: $e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> toggleMic() async {
    if (listening) {
      await stt.stop();
      setState(() => listening = false);
      return;
    }
    if (!sttReady) {
      sttReady = await stt.initialize(
        onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted) setState(() => listening = false);
        },
        onError: (e) {
          if (mounted) setState(() => status = '음성인식 오류: ${e.errorMsg}');
        },
      );
      if (!sttReady) {
        setState(() => status = '마이크 권한 또는 음성인식을 사용할 수 없어요.');
        return;
      }
    }
    setState(() {
      listening = true;
      transcript = '';
    });
    await stt.listen(
      listenOptions: SpeechListenOptions(
        localeId: 'ko_KR',
        listenFor: const Duration(seconds: 20),
        pauseFor: const Duration(seconds: 3),
      ),
      onResult: (r) {
        setState(() => transcript = r.recognizedWords);
        if (r.finalResult) {
          setState(() => listening = false);
          submit(r.recognizedWords);
        }
      },
    );
  }

  Future<void> remove(BabyEvent e) async {
    try {
      await api.delete(e.id);
      await refresh();
    } catch (err) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('삭제 실패: $err')));
    }
  }

  Future<void> askAi() async {
    final q = question.text.trim();
    if (q.isEmpty || busy) return;
    setState(() {
      busy = true;
      answer = '생각 중…';
    });
    try {
      final a = await api.ask(q);
      setState(() => answer = a);
      question.clear();
    } catch (e) {
      setState(() => answer = '오류: $e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _openSettings() async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => SettingsPage(api: api)));
    if (changed == true) refresh();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [_homePage(), _recordsPage(), _aiPage()];
    return Scaffold(
      appBar: AppBar(
        title: Text(['BabyMind', '육아 기록', 'AI에게 질문'][tab], style: const TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () => refresh()),
          IconButton(icon: const Icon(Icons.settings), onPressed: _openSettings),
        ],
      ),
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerLowest,
      body: pages[tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: '오늘'),
          NavigationDestination(icon: Icon(Icons.list_alt), label: '기록'),
          NavigationDestination(icon: Icon(Icons.auto_awesome), label: 'AI'),
        ],
      ),
    );
  }

  // ---------- 오늘 ----------
  Widget _homePage() {
    final s = summary;
    final last = s?.lastFormulaAt;
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(children: [
            _stat('🍼', '분유', '${s?.formulaMl.toInt() ?? 0}ml', '${s?.formulaCount ?? 0}회'),
            _stat('😴', '수면', _minutes(s?.sleepMin ?? 0), ''),
            _stat('🧷', '기저귀', '${s?.diaperCount ?? 0}회', ''),
          ]),
          if (last != null)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text('마지막 분유: ${DateFormat('HH:mm').format(last)} (${_ago(last)})',
                  textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54)),
            ),
          const SizedBox(height: 16),
          _voiceCard(),
          const SizedBox(height: 16),
          _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Text('오늘 기록', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const Spacer(),
              TextButton(onPressed: () => setState(() => tab = 1), child: const Text('전체보기')),
            ]),
            if (today.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: Text('아직 기록이 없어요.\n마이크를 눌러 첫 기록을 남겨보세요.', textAlign: TextAlign.center)),
              ),
            ...today.take(8).map(_eventTile),
          ])),
        ],
      ),
    );
  }

  Widget _voiceCard() {
    return _card(Column(children: [
      Text(listening ? '듣고 있어요…' : '그냥 말해주세요', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
      const SizedBox(height: 6),
      Text(listening ? transcript : '“11시10분에 분유 180 먹었어”\n“8시부터 9시반까지 잤어”',
          textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54)),
      const SizedBox(height: 14),
      GestureDetector(
        onTap: busy ? null : toggleMic,
        child: CircleAvatar(
          radius: 38,
          backgroundColor: listening ? Colors.red : Colors.indigo,
          child: busy
              ? const CircularProgressIndicator(color: Colors.white)
              : Icon(listening ? Icons.stop : Icons.mic, color: Colors.white, size: 34),
        ),
      ),
      const SizedBox(height: 10),
      Text(status, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: Colors.black54)),
      const SizedBox(height: 10),
      Row(children: [
        Expanded(
          child: TextField(
            controller: input,
            decoration: const InputDecoration(hintText: '직접 입력', isDense: true, border: OutlineInputBorder()),
            onSubmitted: submit,
          ),
        ),
        IconButton(icon: const Icon(Icons.send), onPressed: busy ? null : () => submit(input.text)),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        _quick('🍼', '분유', '방금 분유 먹었어'),
        _quick('💩', '응가', '방금 응가했어'),
        _quick('💧', '쉬', '방금 쉬했어'),
        _quick('😴', '잠듦', '방금 잠들었어'),
      ]),
    ]));
  }

  Widget _quick(String icon, String label, String text) => Expanded(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 3),
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 8)),
            onPressed: busy ? null : () => submit(text),
            child: Column(children: [Text(icon, style: const TextStyle(fontSize: 20)), Text(label)]),
          ),
        ),
      );

  // ---------- 기록 ----------
  Widget _recordsPage() {
    if (events.isEmpty) {
      return RefreshIndicator(
        onRefresh: refresh,
        child: ListView(children: const [Padding(padding: EdgeInsets.all(48), child: Center(child: Text('최근 7일 기록이 없어요.')))]),
      );
    }
    final groups = <String, List<BabyEvent>>{};
    for (final e in events) {
      final t = e.startedAt;
      groups.putIfAbsent('${t.month}월 ${t.day}일 (${_weekday(t)})', () => []).add(e);
    }
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        children: [
          for (final g in groups.entries) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
              child: Text(g.key, style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
            ...g.value.map((e) => Dismissible(
                  key: ValueKey(e.id),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    color: Colors.red,
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    child: const Icon(Icons.delete, color: Colors.white),
                  ),
                  confirmDismiss: (_) => _confirmDelete(e),
                  onDismissed: (_) => remove(e),
                  child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: _eventTile(e)),
                )),
          ],
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('왼쪽으로 밀면 삭제됩니다.', textAlign: TextAlign.center, style: TextStyle(color: Colors.black45)),
          ),
        ],
      ),
    );
  }

  Future<bool> _confirmDelete(BabyEvent e) async =>
      await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('기록 삭제'),
          content: Text('${e.label} 기록을 삭제할까요?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('취소')),
            TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('삭제')),
          ],
        ),
      ) ??
      false;

  // ---------- AI ----------
  Widget _aiPage() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        Expanded(
          child: answer.isEmpty
              ? const Center(
                  child: Text('저장된 기록을 바탕으로 질문해 보세요.\n예: 오늘 분유 총 얼마나 먹었어?', textAlign: TextAlign.center))
              : SingleChildScrollView(child: _card(Text(answer, style: const TextStyle(fontSize: 16)))),
        ),
        Row(children: [
          Expanded(
            child: TextField(
              controller: question,
              decoration: const InputDecoration(hintText: '예: 마지막 분유 언제 먹었어?', border: OutlineInputBorder()),
              onSubmitted: (_) => askAi(),
            ),
          ),
          IconButton(icon: const Icon(Icons.arrow_upward), onPressed: busy ? null : askAi),
        ]),
      ]),
    );
  }

  // ---------- 공용 위젯 ----------
  Widget _card(Widget child) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: const [BoxShadow(color: Color(0x11000000), blurRadius: 12)],
        ),
        child: child,
      );

  Widget _stat(String icon, String title, String value, String sub) => Expanded(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
          child: Column(children: [
            Text(icon, style: const TextStyle(fontSize: 24)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            Text(sub.isEmpty ? title : '$title · $sub', style: const TextStyle(fontSize: 12, color: Colors.black54)),
          ]),
        ),
      );

  Widget _eventTile(BabyEvent e) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: CircleAvatar(backgroundColor: Colors.indigo.shade50, child: Text(e.icon, style: const TextStyle(fontSize: 20))),
        title: Text(e.label, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: (e.note?.isNotEmpty ?? false) ? Text(e.note!) : null,
        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
          if (e.source != 'app') const Padding(padding: EdgeInsets.only(right: 4), child: Icon(Icons.speaker, size: 16, color: Colors.black38)),
          Text(DateFormat('HH:mm').format(e.startedAt), style: const TextStyle(color: Colors.black54)),
        ]),
      );

  String _minutes(int m) => m >= 60 ? '${m ~/ 60}시간 ${m % 60}분' : '$m분';

  String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inMinutes < 1) return '방금';
    if (d.inMinutes < 60) return '${d.inMinutes}분 전';
    return '${d.inHours}시간 ${d.inMinutes % 60}분 전';
  }

  String _weekday(DateTime t) => const ['월', '화', '수', '목', '금', '토', '일'][t.weekday - 1];
}

class SettingsPage extends StatefulWidget {
  final Api api;
  const SettingsPage({super.key, required this.api});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final url = TextEditingController(text: widget.api.baseUrl);
  late final token = TextEditingController(text: widget.api.token);
  String result = '';

  Future<void> saveAndTest() async {
    await widget.api.save(url.text, token.text);
    setState(() => result = '연결 확인 중…');
    try {
      await widget.api.health();
      await widget.api.summary(); // 인증 키까지 확인
      setState(() => result = '✓ 서버 연결 성공');
    } catch (e) {
      setState(() => result = '✗ $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('서버 설정')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: url,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: '서버 주소',
            hintText: 'http://192.168.0.10:8000',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: token,
          decoration: const InputDecoration(
            labelText: '인증 키 (서버 .env의 BABYMIND_TOKEN, 없으면 비워두기)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(onPressed: saveAndTest, child: const Text('저장하고 연결 확인')),
        const SizedBox(height: 12),
        Text(result),
        const SizedBox(height: 24),
        OutlinedButton(onPressed: () => Navigator.pop(context, true), child: const Text('완료')),
      ]),
    );
  }
}
