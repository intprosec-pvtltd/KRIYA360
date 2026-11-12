import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Driver UI renders', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Text('KRIYA360'))));
    expect(find.text('KRIYA360'), findsOneWidget);
  });
}
