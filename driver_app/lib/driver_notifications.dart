import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// On-device reminders. Mobile OS battery restrictions can delay alarms.
/// Live assignment changes require the app to reconnect or a separate push service.
class DriverNotifications {
  static final FlutterLocalNotificationsPlugin plugin = FlutterLocalNotificationsPlugin();
  static bool initialized = false;
  static const details = NotificationDetails(android: AndroidNotificationDetails(
    'kriya360_ops', 'KRIYA360 Driver Alerts',
    channelDescription: 'Attendance and delivery task notifications',
    importance: Importance.high, priority: Priority.high,
  ));

  static Future<void> initialize() async {
    if (initialized) return;
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    await plugin.initialize(const InitializationSettings(android: android));
    await plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
    initialized = true;
  }

  static int idOf(String text) {
    var h = 0;
    for (final c in text.codeUnits) { h = ((h * 31) + c) & 0x7fffffff; }
    return h;
  }

  static Future<void> show(String key,String title,String body) async {
    try { await initialize(); await plugin.show(idOf(key),title,body,details); } catch (_) {}
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
    } catch (_) {}
  }

  static Future<void> cancel(String key) async {
    try { await plugin.cancel(idOf(key)); } catch (_) {}
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
    } catch (_) {}
  }

  static Future<void> syncTasks(List tasks) async {
    for(final raw in tasks) {
      if(raw is! Map)continue;
      final t=raw;
      final id='${t['id']??''}';
      if(id.isEmpty)continue;
      if(t['status']=='completed'||t['status']=='cancelled') {
        await cancel('deadline-warning-$id'); await cancel('deadline-due-$id');
        continue;
      }
      final at=DateTime.tryParse('${t['due_at']??''}');
      if(at==null)continue;
      await schedule('deadline-warning-$id','Delivery deadline in 5 minutes','${t['title']??'Delivery'} must be completed soon.',at.subtract(const Duration(minutes:5)));
      await schedule('deadline-due-$id','Delivery deadline reached','${t['title']??'Delivery'} is due now. Report delay if necessary.',at);
    }
  }
}
