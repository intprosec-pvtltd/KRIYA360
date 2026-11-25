import 'dart:ui';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// On-device reminders. Mobile OS battery restrictions can delay alarms.
/// Live assignment changes require the app to reconnect or a separate push service.
class DriverNotifications {
  static final FlutterLocalNotificationsPlugin plugin = FlutterLocalNotificationsPlugin();
  static bool initialized = false;
  static Future<void>? _initializing;
  static VoidCallback? onTap;
  static bool pendingTap = false;
  static void _tap() { if (onTap != null) { onTap!(); } else { pendingTap = true; } }
  static final Set<String> _knownTasks = {};

  static const details = NotificationDetails(android: AndroidNotificationDetails(
    'kriya360_ops_v2', 'KRIYA360 Driver Alerts',
    icon: 'ic_kriya_notification', color: Color(0xffF47A20),
    playSound: true, enableVibration: true,
    channelDescription: 'Attendance and delivery task notifications',
    importance: Importance.high, priority: Priority.high,
  ));

  static Future<void> initialize() async {
    if (initialized) return;
    await (_initializing ??= _initialize());
  }
  static Future<void> _initialize() async {
    try {
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));
    const android = AndroidInitializationSettings('ic_kriya_notification');
    await plugin.initialize(const InitializationSettings(android: android), onDidReceiveNotificationResponse: (_) => _tap());
    final launch = await plugin.getNotificationAppLaunchDetails();
    if (launch?.didNotificationLaunchApp == true) _tap();
    await plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
    initialized = true;
    } finally { _initializing = null; }
  }

  static int idOf(String text) {
    var h = 0;
    for (final c in text.codeUnits) { h = ((h * 31) + c) & 0x7fffffff; }
    return h;
  }

  static Future<void> show(String key,String title,String body) async {
    try { await initialize(); await plugin.show(idOf(key),title,body,details); } catch (e) { debugPrint('KRIYA360 notification operation failed: ${e.runtimeType}'); }
  }

  static Future<void> schedule(String key,String title,String body,DateTime at, {bool daily=false}) async {
    try {
      await initialize();
      final when = tz.TZDateTime.from(at,tz.local);
      if (when.isBefore(tz.TZDateTime.now(tz.local))) return;
      await plugin.zonedSchedule(idOf(key),title,body,when,details,
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
        matchDateTimeComponents: daily ? DateTimeComponents.time : null);
    } catch (e) { debugPrint('KRIYA360 notification operation failed: ${e.runtimeType}'); }
  }

  static Future<void> cancel(String key) async {
    try { await plugin.cancel(idOf(key)); } catch (e) { debugPrint('KRIYA360 notification operation failed: ${e.runtimeType}'); }
  }

  static Future<void> syncShift(String shiftText,bool onShift) async {
    try {
      await initialize();
      await cancel('shift-reminder');
      await cancel('shift-missed');
      if (onShift) return;
      final parts=shiftText.split(':').map(int.parse).toList();
      final now=tz.TZDateTime.now(tz.local);
      var shift=tz.TZDateTime(tz.local,now.year,now.month,now.day,parts[0],parts[1]);
      if (!shift.isAfter(now)) shift=shift.add(const Duration(days:1));
      await schedule('shift-reminder','Shift starts in 5 minutes','Punch in to begin your KRIYA360 shift',shift.subtract(const Duration(minutes:5)),daily:true);
      await schedule('shift-missed','Missed shift check','If you are on duty, remember to punch in',shift.add(const Duration(minutes:5)),daily:true);
    } catch (e) { debugPrint('KRIYA360 notification operation failed: ${e.runtimeType}'); }
  }

  static Future<void> clearReminders() async {
    try { await initialize(); await plugin.cancelAll(); _knownTasks.clear(); pendingTap = false; } catch (e) { debugPrint('Notification cleanup failed: ${e.runtimeType}'); }
  }
  static Future<void> syncTasks(List tasks) async {
    final current = tasks.whereType<Map>().map((t) => '${t['id'] ?? ''}').where((id) => id.isNotEmpty).toSet();
    for (final id in _knownTasks.difference(current)) {
      await cancel('deadline-warning-$id'); await cancel('deadline-due-$id');
    }
    _knownTasks..clear()..addAll(current);
    for(final raw in tasks) {
      if(raw is! Map)continue;
      final t=raw;
      final id='${t['id']??''}';
      if(id.isEmpty)continue;
      if(!['assigned','in_progress','ready_for_acceptance'].contains(t['status'])) {
        await cancel('deadline-warning-$id'); await cancel('deadline-due-$id');
        continue;
      }
      final at=DateTime.tryParse('${t['due_at']??''}');
      await cancel('deadline-warning-$id'); await cancel('deadline-due-$id');
      if(at==null)continue;
      await schedule('deadline-warning-$id','Delivery deadline approaching','${t['title']??'Delivery'} is approaching its deadline. Open My Tasks for current details.',at.subtract(const Duration(minutes:5)));
      await schedule('deadline-due-$id','Delivery deadline reached','${t['title']??'Delivery'} is due now. Report delay if necessary.',at);
    }
  }
}
