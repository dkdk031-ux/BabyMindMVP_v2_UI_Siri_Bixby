import 'package:babymind/api.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('BabyEvent label', () {
    final e = BabyEvent.fromJson({
      'id': 1,
      'type': 'formula',
      'started_at': '2026-10-10T11:10:00+09:00',
      'ended_at': null,
      'amount': 500,
      'unit': 'ml',
      'note': null,
      'source': 'bixby',
    });
    expect(e.label, '분유 500ml');
    expect(e.icon, '🍼');
  });
}
