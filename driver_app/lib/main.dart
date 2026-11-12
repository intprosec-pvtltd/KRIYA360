import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'driver_notifications.dart';

const navy=Color(0xff081F45), orange=Color(0xffF47A20), blue=Color(0xff226FC1), bg=Color(0xffF4F7FB);
// For Android emulator 10.0.2.2; physical device: --dart-define=API_URL=http://YOUR_PC_LAN_IP:8000
const apiUrl=String.fromEnvironment('API_URL',defaultValue:'http://10.0.2.2:8000');
const secure=FlutterSecureStorage();
final GlobalKey<NavigatorState> kriyaNavigatorKey=GlobalKey<NavigatorState>();
void main(){WidgetsFlutterBinding.ensureInitialized();runApp(const KriyaApp());}

final labels=<String,Map<String,String>>{
 'en':{'home':'Home','tasks':'My Tasks','expenses':'Expenses','profile':'Profile','punchIn':'Punch In','punchOut':'Punch Out','onShift':'You are on shift','offShift':'You are off shift','active':'Active Deliveries','assigned':'Assigned Deliveries','done':'Completed','sos':'EMERGENCY SOS','sosQuestion':'Do you want to send an emergency alert with your location to management?','confirm':'Confirm SOS','cancel':'Cancel','start':'Start Delivery','navigate':'Navigate','complete':'Complete Delivery','otp':'Recipient OTP','photo':'Delivery Photo','submit':'Submit','expense':'Add Expense','amount':'Amount (₹)','note':'Upload Payment Evidence','language':'Language','signOut':'Sign Out','refresh':'Refresh','attendance':'Attendance','vehicle':'Vehicle details','face':'Enroll Face Photo','pending':'Pending','verify':'OTP + photo verification','hello':'Welcome back'},
 'hi':{'home':'होम','tasks':'मेरे कार्य','expenses':'खर्च','profile':'प्रोफ़ाइल','punchIn':'पंच इन','punchOut':'पंच आउट','onShift':'आप ड्यूटी पर हैं','offShift':'आप ड्यूटी पर नहीं हैं','active':'सक्रिय डिलीवरी','assigned':'सौंपी गई डिलीवरी','done':'पूर्ण','sos':'आपातकालीन SOS','sosQuestion':'क्या आप अपना स्थान प्रबंधन को भेजकर आपातकालीन अलर्ट भेजना चाहते हैं?','confirm':'SOS की पुष्टि करें','cancel':'रद्द करें','start':'डिलीवरी शुरू करें','navigate':'रास्ता देखें','complete':'डिलीवरी पूरी करें','otp':'प्राप्तकर्ता OTP','photo':'डिलीवरी फ़ोटो','submit':'जमा करें','expense':'खर्च जोड़ें','amount':'राशि (₹)','note':'विवरण','language':'भाषा','signOut':'लॉग आउट','refresh':'रीफ़्रेश','attendance':'उपस्थिति','vehicle':'वाहन विवरण','face':'चेहरे की फोटो दर्ज करें','pending':'लंबित','verify':'OTP + फ़ोटो सत्यापन','hello':'स्वागत है'},
 'kn':{'home':'ಮುಖಪುಟ','tasks':'ನನ್ನ ಕೆಲಸಗಳು','expenses':'ವೆಚ್ಚಗಳು','profile':'ಪ್ರೊಫೈಲ್','punchIn':'ಪಂಚ್ ಇನ್','punchOut':'ಪಂಚ್ ಔಟ್','onShift':'ನೀವು ಕರ್ತವ್ಯದಲ್ಲಿದ್ದೀರಿ','offShift':'ನೀವು ಕರ್ತವ್ಯದಲ್ಲಿಲ್ಲ','active':'ಚಾಲ್ತಿಯ ವಿತರಣೆಗಳು','assigned':'ನಿಯೋಜಿತ ವಿತರಣೆಗಳು','done':'ಪೂರ್ಣಗೊಂಡಿದೆ','sos':'ತುರ್ತು SOS','sosQuestion':'ನಿಮ್ಮ ಸ್ಥಳದೊಂದಿಗೆ ನಿರ್ವಹಣೆಗೆ ತುರ್ತು ಸಂದೇಶ ಕಳುಹಿಸಬೇಕೇ?','confirm':'SOS ಖಚಿತಪಡಿಸಿ','cancel':'ರದ್ದು','start':'ವಿತರಣೆ ಪ್ರಾರಂಭಿಸಿ','navigate':'ದಾರಿ ತೋರಿಸಿ','complete':'ವಿತರಣೆ ಪೂರ್ಣಗೊಳಿಸಿ','otp':'ಸ್ವೀಕರಿಸುವವರ OTP','photo':'ವಿತರಣೆಯ ಚಿತ್ರ','submit':'ಸಲ್ಲಿಸಿ','expense':'ವೆಚ್ಚ ಸೇರಿಸಿ','amount':'ಮೊತ್ತ (₹)','note':'ಟಿಪ್ಪಣಿ','language':'ಭಾಷೆ','signOut':'ಲಾಗ್ ಔಟ್','refresh':'ರಿಫ್ರೆಶ್','attendance':'ಹಾಜರಾತಿ','vehicle':'ವಾಹನ ವಿವರಗಳು','face':'ಮುಖದ ಚಿತ್ರ ದಾಖಲಿಸಿ','pending':'ಬಾಕಿ','verify':'OTP + ಚಿತ್ರ ಪರಿಶೀಲನೆ','hello':'ಸ್ವಾಗತ'},
 'ta':{'home':'முகப்பு','tasks':'என் பணிகள்','expenses':'செலவுகள்','profile':'சுயவிவரம்','punchIn':'பஞ்ச் இன்','punchOut':'பஞ்ச் அவுட்','onShift':'நீங்கள் பணியில் உள்ளீர்கள்','offShift':'நீங்கள் பணியில் இல்லை','active':'செயலில் உள்ள டெலிவரிகள்','assigned':'ஒதுக்கப்பட்ட டெலிவரிகள்','done':'முடிந்தது','sos':'அவசர SOS','sosQuestion':'உங்கள் இருப்பிடத்துடன் மேலாளருக்கு அவசரச் செய்தி அனுப்ப வேண்டுமா?','confirm':'SOS உறுதிப்படுத்து','cancel':'ரத்து','start':'டெலிவரி தொடங்கு','navigate':'வழிகாட்டு','complete':'டெலிவரி முடி','otp':'பெறுநர் OTP','photo':'டெலிவரி படம்','submit':'சமர்ப்பி','expense':'செலவு சேர்','amount':'தொகை (₹)','note':'குறிப்புகள்','language':'மொழி','signOut':'வெளியேறு','refresh':'புதுப்பி','attendance':'வருகை','vehicle':'வாகன விவரங்கள்','face':'முகப் புகைப்படம் பதிவு','pending':'நிலுவை','verify':'OTP + படம் சரிபார்ப்பு','hello':'வரவேற்பு'},
 'te':{'home':'హోమ్','tasks':'నా పనులు','expenses':'ఖర్చులు','profile':'ప్రొఫైల్','punchIn':'పంచ్ ఇన్','punchOut':'పంచ్ అవుట్','onShift':'మీరు విధుల్లో ఉన్నారు','offShift':'మీరు విధుల్లో లేరు','active':'కొనసాగుతున్న డెలివరీలు','assigned':'కేటాయించిన డెలివరీలు','done':'పూర్తయింది','sos':'అత్యవసర SOS','sosQuestion':'మీ స్థానంతో నిర్వహణకు అత్యవసర సందేశం పంపాలా?','confirm':'SOS నిర్ధారించు','cancel':'రద్దు','start':'డెలివరీ ప్రారంభించు','navigate':'దారి చూపు','complete':'డెలివరీ పూర్తి','otp':'గ్రహీత OTP','photo':'డెలివరీ ఫోటో','submit':'సమర్పించు','expense':'ఖర్చు చేర్చు','amount':'మొత్తం (₹)','note':'వివరాలు','language':'భాష','signOut':'లాగ్ అవుట్','refresh':'రిఫ్రెష్','attendance':'హాజరు','vehicle':'వాహన వివరాలు','face':'ముఖ ఫోటో నమోదు','pending':'పెండింగ్','verify':'OTP + ఫోటో నిర్ధారణ','hello':'స్వాగతం'}
};

class Api{
 String? token;
 Future<dynamic> call(String path,{String method='GET',Map<String,dynamic>? json,Map<String,String>? fields,String? photo})async{
  final url=Uri.parse('$apiUrl/api$path');final headers={'Authorization':'Bearer ${token??''}'};
  http.Response response;
  if(photo!=null){final r=http.MultipartRequest(method,url)..headers.addAll(headers);r.fields.addAll(fields??{});r.files.add(await http.MultipartFile.fromPath('image',photo));response=await http.Response.fromStream(await r.send().timeout(const Duration(seconds:25)));}
  else{response=await http.Request(method,url).sendWithBody(json,headers);}
  dynamic payload;try{payload=jsonDecode(response.body);}catch(_){payload={};}
  if(response.statusCode>=400)throw Exception(payload is Map?payload['detail']??'HTTP ${response.statusCode}':'HTTP ${response.statusCode}');return payload;
 }
}
extension HttpSend on http.Request{
 Future<http.Response> sendWithBody(Map<String,dynamic>? data,Map<String,String> headers)async{
  this.headers.addAll(headers);if(data!=null){this.headers['Content-Type']='application/json';body=jsonEncode(data);}return http.Response.fromStream(await send().timeout(const Duration(seconds:20)));
 }
}
final api=Api();
class KriyaApp extends StatefulWidget{const KriyaApp({super.key});@override State<KriyaApp>createState()=>_KriyaAppState();}
class _KriyaAppState extends State<KriyaApp>{String? token;Map<String,dynamic>? user;String lang='en';bool loading=true;bool pending=false;
 @override void initState(){super.initState();restore();}
 Future<void> restore()async{
  final t=await secure.read(key:'token');
  if(t!=null){
    api.token=t;
    try{
      final data=Map<String,dynamic>.from(await api.call('/me'));
      user=data;token=t;pending=data['role']=='driver'&&data['license_status']!='approved';lang=data['language']??'en';
    }catch(_){
      try{
        final data=Map<String,dynamic>.from(await api.call('/onboarding/status'));
        user=data;token=t;pending=true;lang=data['language']??'en';
      }catch(_){await secure.delete(key:'token');api.token=null;user=null;token=null;pending=false;}
    }
  }
  if(mounted){setState(()=>loading=false);if(token!=null&&!pending)WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)requestStartupPermissions();});}
 }
 Future<void> requestStartupPermissions() async {
  final prefs=await SharedPreferences.getInstance();
  if(prefs.getBool('kriya_permissions_explained')==true)return;
  if(!mounted||kriyaNavigatorKey.currentContext==null)return;
  final accepted=await showDialog<bool>(context:kriyaNavigatorKey.currentContext!,builder:(ctx)=>AlertDialog(
    title:const Text('Enable driver permissions'),
    content:const Text('KRIYA360 uses location for attendance, shift tracking, routes and SOS. Notifications inform you about assignments, deadlines and shifts. Camera and photos are requested when you upload evidence. You may change permissions in Android Settings.'),
    actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:const Text('Not now')),FilledButton(onPressed:()=>Navigator.pop(ctx,true),child:const Text('Continue'))],
  ));
  if(accepted!=true)return;
  await prefs.setBool('kriya_permissions_explained',true);
  try{await DriverNotifications.initialize();}catch(_){}
  try{
    var permission=await Geolocator.checkPermission();
    if(permission==LocationPermission.denied)await Geolocator.requestPermission();
  }catch(_){}
}
 Future<void> login(String phone,String pin)async{final x=await api.call('/auth/login',method:'POST',json:{'phone':phone,'pin':pin});if(x['user']['role']!='driver')throw Exception('Driver account required');api.token=x['access_token'];pending=x['enrollment_only']==true || x['user']['license_status']!='approved';await secure.write(key:'token',value:api.token);setState((){token=api.token;user=Map<String,dynamic>.from(x['user']);lang=user?['language'] ?? 'en';});if(!pending)WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)requestStartupPermissions();});}
 Future<void> updateUser(Map<String,dynamic>u)async{setState(()=>user=u);}
 Future<void> refreshEnrollment()async{
  final data=Map<String,dynamic>.from(await api.call('/onboarding/status'));
  if(!mounted)return;
  setState((){user=data;pending=data['license_status']!='approved';});
  if(data['license_status']=='approved'){
    // An enrollment-scoped token must never be promoted to a full-access token.
    await logout();
  }
 }
 Future<void> changeLang(String next)async{await api.call('/me/language',method:'PATCH',json:{'language':next});setState(()=>lang=next);}
 Future<void> logout()async{await secure.delete(key:'token');api.token=null;setState((){token=null;user=null;pending=false;});}
 @override Widget build(BuildContext context){return MaterialApp(navigatorKey:kriyaNavigatorKey,debugShowCheckedModeBanner:false,title:'KRIYA360 Driver',supportedLocales:const[Locale('en'),Locale('hi'),Locale('kn'),Locale('ta'),Locale('te')],localizationsDelegates:const [GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate, GlobalWidgetsLocalizations.delegate],locale:Locale(lang),theme:ThemeData(useMaterial3:true,scaffoldBackgroundColor:bg,colorScheme:ColorScheme.fromSeed(seedColor:navy),fontFamily:'Roboto',appBarTheme:const AppBarTheme(backgroundColor:bg,foregroundColor:navy)),home:loading?const KriyaBrandSplash():token==null?LoginPage(onLogin:login):pending?PendingDriverPage(user:user!,onBack:logout,onRefresh:refreshEnrollment):user?['pin_change_required']==true?PinChangePage(onDone:()async{final fresh=Map<String,dynamic>.from(user!);fresh['pin_change_required']=false;setState(()=>user=fresh);}):DriverHome(user:user!,lang:lang,onUser:updateUser,onLanguage:changeLang,onLogout:logout));}
}
/// Distinct emergency action; tapping retains the existing SOS confirmation dialog.
class KriyaSosNavIcon extends StatelessWidget{
 const KriyaSosNavIcon({super.key});
 @override Widget build(BuildContext context)=>Container(
   width:54,height:36,
   decoration:BoxDecoration(color:const Color(0xffD82D43),borderRadius:BorderRadius.circular(12)),
   alignment:Alignment.center,
   child:const Icon(Icons.sos,color:Colors.white,size:24),
 );
}

class PendingDriverPage extends StatefulWidget{
 final Map<String,dynamic> user;final Future<void> Function() onBack;final Future<void> Function() onRefresh;
 const PendingDriverPage({super.key,required this.user,required this.onBack,required this.onRefresh});
 @override State<PendingDriverPage> createState()=>_PendingDriverPageState();
}
class _PendingDriverPageState extends State<PendingDriverPage>{
 final picker=ImagePicker();bool busy=false;bool consent=false;
 Future<void> uploadLicense(ImageSource source)async{
  if(!consent){toast(context,'Consent is needed before submitting your driving licence proof');return;}
  final photo=await picker.pickImage(source:source,imageQuality:85);
  if(photo==null)return;
  setState(()=>busy=true);
  try{
   await api.call('/onboarding/license',method:'POST',photo:photo.path);
   await widget.onRefresh();
   if(mounted)toast(context,'Licence proof submitted. Management approval is required before you can use the app.');
  }catch(e){if(mounted)toast(context,'Upload failed: $e');}
  finally{if(mounted)setState(()=>busy=false);}
 }
 @override Widget build(BuildContext context){
  final status=licenseStatusOf(widget.user);
  final canUpload=status=='missing'||status=='rejected';
  final note=(widget.user['license_review_note']??'').toString().trim();
  return Scaffold(
   appBar:AppBar(title:const Text('Licence verification'),automaticallyImplyLeading:false),
   body:SafeArea(child:ListView(padding:const EdgeInsets.all(20),children:[
    Container(
     padding:const EdgeInsets.all(22),
     decoration:BoxDecoration(gradient:const LinearGradient(colors:[navy,Color(0xff16528c)]),borderRadius:BorderRadius.circular(24)),
     child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      const Icon(Icons.verified_user_outlined,color:orange,size:36),
      const SizedBox(height:12),
      const Text('Complete your driver verification',style:TextStyle(color:Colors.white,fontWeight:FontWeight.w900,fontSize:24)),
      const SizedBox(height:8),
      Text(
       status=='pending'
         ? 'Your licence proof has been sent to management. You can access the app after approval.'
         : status=='rejected'
            ? 'Your earlier licence proof was not approved. Please upload a clearer or correct document to continue.'
            : 'Your manager created your account. Upload your driving licence proof to continue into the app.',
       style:const TextStyle(color:Colors.white70,height:1.35),
      ),
      const SizedBox(height:14),
      Wrap(spacing:10,runSpacing:10,children:[
       statusBadge(status),
       Container(
        padding:const EdgeInsets.symmetric(horizontal:12,vertical:8),
        decoration:BoxDecoration(color:Colors.white.withValues(alpha:.12),borderRadius:BorderRadius.circular(999)),
        child:Text('Licence: ${widget.user['license_no']??'—'}',style:const TextStyle(color:Colors.white,fontWeight:FontWeight.w700)),
       )
      ])
     ]),
    ),
    const SizedBox(height:18),
    Container(margin:const EdgeInsets.only(bottom:12),padding:const EdgeInsets.all(17),decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(15),border:Border.all(color:const Color(0xffe6edf5))),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Text('${widget.user['name']??''}',style:const TextStyle(color:navy,fontSize:20,fontWeight:FontWeight.w900)),
      const SizedBox(height:8),
      Text('Phone: ${widget.user['phone']??''}',style:const TextStyle(color:Colors.blueGrey)),
      const SizedBox(height:16),
      const Text('What you need to do',style:TextStyle(color:navy,fontWeight:FontWeight.w800,fontSize:16)),
      const SizedBox(height:10),
      bulletPoint('Upload a clear image of your driving licence.'),
      bulletPoint('Management will review the proof and confirm the licence details.'),
      bulletPoint('If the proof is rejected, you must upload it again before entering the app.'),
      if(note.isNotEmpty)...[const SizedBox(height:16),const Text('Manager note',style:TextStyle(color:navy,fontWeight:FontWeight.w800,fontSize:16)),const SizedBox(height:6),Text(note,style:const TextStyle(color:Colors.blueGrey,height:1.35))],
      const SizedBox(height:18),
      CheckboxListTile(
       value:consent,
       contentPadding:EdgeInsets.zero,
       onChanged:(v)=>setState(()=>consent=v??false),
       title:const Text('I consent to sharing my driving licence for restricted management verification.'),
      ),
      const SizedBox(height:4),
      Row(children:[
       Expanded(child:FilledButton.icon(style:filled(),onPressed:busy||!canUpload?null:()=>uploadLicense(ImageSource.gallery),icon:const Icon(Icons.upload_file),label:Text(busy?'Uploading...':'Upload licence proof'))),
      ]),
      const SizedBox(height:10),
      if(canUpload)Center(child:TextButton.icon(onPressed:busy?null:()=>uploadLicense(ImageSource.camera),icon:const Icon(Icons.camera_alt_outlined),label:const Text('Take photo instead')))
      else Center(child:Text(status=='pending'?'Upload locked until manager review.':'Approved drivers can continue after signing in again.',style:const TextStyle(color:Colors.blueGrey),textAlign:TextAlign.center)),
    ])),
    const SizedBox(height:18),
    OutlinedButton.icon(
      onPressed:busy?null:()async{
        setState(()=>busy=true);
        try{await widget.onRefresh();}catch(e){if(mounted)toast(context,'Unable to refresh verification status: $e');}
        finally{if(mounted)setState(()=>busy=false);}
      },
      icon:const Icon(Icons.refresh),label:const Text('Check manager approval status'),
    ),
    const SizedBox(height:8),
    FilledButton.tonal(onPressed:busy?null:widget.onBack,child:const Text('Sign out')),
   ])),
  );
 }
}

/// Company identity is shown once, with its tagline already present in the supplied art.
class BrandCompanyFooter extends StatelessWidget {
 const BrandCompanyFooter({super.key,this.logoHeight=40});
 final double logoHeight;
 @override
 Widget build(BuildContext context) => Column(
   mainAxisSize: MainAxisSize.min,
   children: [
     const Text('POWERED BY',textAlign:TextAlign.center,style:TextStyle(color:Colors.blueGrey,fontSize:10,fontWeight:FontWeight.w700,letterSpacing:2)),
     const SizedBox(height:8),
     Image.asset('assets/company_logo.png',height:logoHeight,fit:BoxFit.contain,filterQuality:FilterQuality.high),
   ],
 );
}
String licenseStatusOf(Map<String,dynamic> user){
 final raw='${user['license_status']??''}'.toLowerCase().trim();
 if(raw.isNotEmpty)return raw;
 final note='${user['license_review_note']??''}'.toLowerCase();
 if(user['license_verified']==true&&user['approved']==true)return 'approved';
 if(user['license_url']==null)return 'missing';
 if(note.contains('rejected')||note.contains('upload again')||note.contains('re-upload'))return 'rejected';
 return 'pending';
}
String licenseStatusLabel(String status)=>switch(status){'approved'=>'Approved','pending'=>'Pending review','rejected'=>'Rejected','missing'=>'Not uploaded',_=>'Unknown'};
Color licenseStatusBg(String status)=>switch(status){'approved'=>const Color(0xffe6f7ec),'pending'=>const Color(0xfffff3dc),'rejected'=>const Color(0xffffebeb),_=>const Color(0xffeef3fb)};
Color licenseStatusFg(String status)=>switch(status){'approved'=>const Color(0xff157347),'pending'=>const Color(0xff946200),'rejected'=>const Color(0xffb02a37),_=>navy};
Widget statusBadge(String status)=>Container(
 padding:const EdgeInsets.symmetric(horizontal:14,vertical:8),
 decoration:BoxDecoration(color:licenseStatusBg(status),borderRadius:BorderRadius.circular(999)),
 child:Text(licenseStatusLabel(status),style:TextStyle(color:licenseStatusFg(status),fontWeight:FontWeight.w800)),
);
Widget bulletPoint(String text)=>Padding(
 padding:const EdgeInsets.only(bottom:8),
 child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[const Padding(padding:EdgeInsets.only(top:3),child:Icon(Icons.check_circle,color:orange,size:18)),const SizedBox(width:8),Expanded(child:Text(text,style:const TextStyle(color:Colors.blueGrey,height:1.35)))]),
);
class KriyaBrandSplash extends StatelessWidget {
 const KriyaBrandSplash({super.key});
 @override Widget build(BuildContext context)=>Scaffold(backgroundColor:Colors.white,body:SafeArea(child:Padding(
  padding:const EdgeInsets.symmetric(horizontal:28,vertical:24),
  child:Column(children:[
   const Spacer(),
   Expanded(
    flex:4,
    child:Center(
     child:Column(mainAxisSize:MainAxisSize.min,children:[
      Image.asset('assets/loading_logo.png',height:140,fit:BoxFit.contain,filterQuality:FilterQuality.high),
      const SizedBox(height:30),
      const SizedBox(width:32,height:32,child:CircularProgressIndicator(strokeWidth:3,color:orange)),
     ]),
    ),
   ),
   const BrandCompanyFooter(logoHeight:46),
   const SizedBox(height:12),
  ]),
 )));
}
class PinChangePage extends StatefulWidget{final Future<void> Function() onDone;const PinChangePage({super.key,required this.onDone});@override State<PinChangePage> createState()=>_PinChangePageState();}
class _PinChangePageState extends State<PinChangePage>{final oldPin=TextEditingController(),newPin=TextEditingController();bool busy=false;
 @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Secure your account')),body:SafeArea(child:Center(child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:420),child:ListView(padding:const EdgeInsets.all(25),shrinkWrap:true,children:[const Icon(Icons.lock_reset,color:orange,size:50),const SizedBox(height:18),const Text('Change your temporary PIN',style:TextStyle(fontSize:25,fontWeight:FontWeight.w800,color:navy)),const SizedBox(height:12),const Text('Management generated a one-time PIN for your imported driver account. Change it before using KRIYA360.'),const SizedBox(height:20),TextField(controller:oldPin,obscureText:true,decoration:decor('Temporary PIN',Icons.key)),const SizedBox(height:12),TextField(controller:newPin,obscureText:true,decoration:decor('New PIN (6 or more characters)',Icons.lock_outline)),const SizedBox(height:20),FilledButton(style:filled(),onPressed:busy?null:()async{setState(()=>busy=true);try{await api.call('/me/change-pin',method:'POST',json:{'old_pin':oldPin.text,'new_pin':newPin.text});await widget.onDone();}catch(e){if(mounted)toast(context,'PIN change failed: $e');}finally{if(mounted)setState(()=>busy=false);}},child:const Text('Save new PIN'))])))));}
class LoginPage extends StatefulWidget{final Future<void> Function(String,String) onLogin;const LoginPage({super.key,required this.onLogin});@override State<LoginPage>createState()=>_LoginPageState();}
class _LoginPageState extends State<LoginPage>{final phone=TextEditingController(),pin=TextEditingController();bool busy=false;@override Widget build(BuildContext context){return Scaffold(backgroundColor:Colors.white,body:SafeArea(child:Center(child:SingleChildScrollView(padding:const EdgeInsets.all(28),child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:430),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Container(decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(20)),padding:const EdgeInsets.symmetric(vertical:12,horizontal:4),child:Image.asset('assets/signin_logo.png',height:120,fit:BoxFit.contain,filterQuality:FilterQuality.high)),const SizedBox(height:30),const Text('Welcome, Driver!',style:TextStyle(fontSize:28,fontWeight:FontWeight.w900,color:navy)),const SizedBox(height:7),const Text('Manage deliveries and stay connected with dispatch.',style:TextStyle(color:Colors.blueGrey)),const SizedBox(height:28),TextField(controller:phone,keyboardType:TextInputType.phone,decoration:decor('Phone number',Icons.phone_outlined)),const SizedBox(height:14),TextField(controller:pin,obscureText:true,decoration:decor('Security PIN',Icons.lock_outline)),const SizedBox(height:23),FilledButton(style:filled(),onPressed:busy?null:()async{setState(()=>busy=true);try{await widget.onLogin(phone.text.trim(),pin.text);}catch(e){toast(context,'Login failed: $e');}finally{if(mounted)setState(()=>busy=false);}},child:Padding(padding:const EdgeInsets.all(13),child:Text(busy?'Signing in...':'Sign In',style:const TextStyle(fontWeight:FontWeight.bold)))),const SizedBox(height:12),const Text('Driver accounts are created by management. Use the PIN given to you by your manager.',textAlign:TextAlign.center,style:TextStyle(color:Colors.blueGrey,fontSize:12)),const SizedBox(height:38),const BrandCompanyFooter(logoHeight:42),const SizedBox(height:12)]))))));}}
InputDecoration decor(String label,IconData icon)=>InputDecoration(labelText:label,prefixIcon:Icon(icon,color:blue),filled:true,fillColor:Colors.white,contentPadding:const EdgeInsets.symmetric(vertical:17,horizontal:15),border:OutlineInputBorder(borderRadius:BorderRadius.circular(12),borderSide:const BorderSide(color:Color(0xffdce5f0))),enabledBorder:OutlineInputBorder(borderRadius:BorderRadius.circular(12),borderSide:const BorderSide(color:Color(0xffdce5f0))));
ButtonStyle filled()=>FilledButton.styleFrom(backgroundColor:orange,foregroundColor:Colors.white,shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(12)));
void toast(BuildContext ctx,String s){if(ctx.mounted)ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content:Text(s)));}
class DriverHome extends StatefulWidget{final Map<String,dynamic> user;final String lang;final Future<void>Function(Map<String,dynamic>) onUser;final Future<void>Function(String) onLanguage;final Future<void>Function() onLogout;const DriverHome({super.key,required this.user,required this.lang,required this.onUser,required this.onLanguage,required this.onLogout});@override State<DriverHome>createState()=>_DriverHomeState();}
class _DriverHomeState extends State<DriverHome>{int tab=0;List tasks=[];List expenses=[];List<Map<String,dynamic>> notifications=[];Set<String> seenNotifications={};final Set<String> _notifiedThisSession={};String _scheduledSignature='';bool busy=false;StreamSubscription<Position>? gpsSub;Timer? poll;final picker=ImagePicker();String tr(String key)=>labels[widget.lang]?[key]??labels['en']![key]??key;
 @override void initState(){super.initState();restoreSeen();DriverNotifications.initialize();load();startPolling();if(widget.user['on_shift']==true)startGps();}
 @override void dispose(){gpsSub?.cancel();poll?.cancel();super.dispose();}
 Future<void> restoreSeen()async{final prefs=await SharedPreferences.getInstance();seenNotifications=(prefs.getStringList('read_notifications')??[]).toSet();}
 Future<void> markNotificationsRead()async{final prefs=await SharedPreferences.getInstance();seenNotifications.addAll(notifications.map((n)=>'${n['id']}'));await prefs.setStringList('read_notifications',seenNotifications.toList());if(mounted)setState((){});}
 Future<void> showNotifications() async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => SafeArea(
      child: Container(
        height: MediaQuery.of(ctx).size.height * .72,
        decoration: const BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 46,
                  height: 5,
                  decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(99)),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Notifications',style: TextStyle(color: navy, fontSize: 22, fontWeight: FontWeight.w900)),
                        SizedBox(height: 6),
                        Text('Shift reminders, new assignments and deadline alerts.',style: TextStyle(color: Colors.blueGrey)),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.pop(ctx),
                    style: IconButton.styleFrom(backgroundColor: Colors.white),
                    icon: const Icon(Icons.close_rounded, color: navy),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Expanded(
                child: notifications.isEmpty
                    ? const Center(child: Text('No notifications right now',style: TextStyle(color: Colors.blueGrey)))
                    : ListView.separated(
                        itemCount: notifications.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (_, index) {
                          final n=notifications[index];
                          final isTask=n['type']=='task_assignment';
                          return Material(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(18),
                            child: InkWell(
                              borderRadius: BorderRadius.circular(18),
                              onTap: () {
                                // Notification cards are actionable: open the corresponding tab.
                                final kind = '${n['type'] ?? ''}';
                                Navigator.of(ctx).pop();
                                if (!mounted) return;
                                setState(() => tab = (
                                  kind == 'task_assignment' ||
                                  kind == 'deadline_warning' ||
                                  kind == 'deadline_missed' ||
                                  kind == 'predicted_delay'
                                ) ? 1 : 0);
                              },
                              child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xffe7edf6))),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  width: 46,
                                  height: 46,
                                  decoration: BoxDecoration(color: (isTask?orange:Colors.redAccent).withValues(alpha:.12),borderRadius: BorderRadius.circular(14)),
                                  child: Icon(isTask?Icons.assignment_outlined:Icons.notifications_active_outlined,color:isTask?orange:Colors.redAccent),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text('${n['title'] ?? ''}',style: const TextStyle(fontWeight: FontWeight.w800,fontSize: 17,color: navy)),
                                      const SizedBox(height: 5),
                                      Text('${n['message'] ?? ''}',style: const TextStyle(color: Colors.blueGrey,height: 1.35)),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
  await markNotificationsRead();
 }

 Future<void> load()async{try{final result=await Future.wait([api.call('/tasks'),api.call('/expenses'),api.call('/me'),api.call('/driver/notifications')]);if(mounted){setState((){tasks=result[0];expenses=result[1];notifications=List<Map<String,dynamic>>.from((result[3] as List).map((n)=>Map<String,dynamic>.from(n)));});await widget.onUser(Map<String,dynamic>.from(result[2]));
      final signature='${result[2]['shift_expected']}|${result[2]['on_shift']}|${tasks.map((t)=>'${t['id']}:${t['status']}:${t['due_at']}').join('|')}';
      if(signature!=_scheduledSignature){_scheduledSignature=signature;DriverNotifications.syncShift('${result[2]['shift_expected']??'09:00'}',result[2]['on_shift']==true);DriverNotifications.syncTasks(tasks);}
      for(final n in notifications){final key='${n['id']}';if(!seenNotifications.contains(key)&&!_notifiedThisSession.contains(key)){_notifiedThisSession.add(key);if(n['type']=='task_assignment'||n['type']=='predicted_delay'||n['type']=='deadline_warning'||n['type']=='deadline_missed')DriverNotifications.show(key,'${n['title']??''}','${n['message']??''}');}}}}catch(e){if(mounted)toast(context,'Refresh failed: $e');}}
 void startPolling(){poll?.cancel();poll=Timer.periodic(const Duration(seconds:12),(_){load();});}
 Future<Position> location()async{if(!await Geolocator.isLocationServiceEnabled())throw Exception('Enable device location');var p=await Geolocator.checkPermission();if(p==LocationPermission.denied)p=await Geolocator.requestPermission();if(p==LocationPermission.denied||p==LocationPermission.deniedForever)throw Exception('Location permission required');return Geolocator.getCurrentPosition(desiredAccuracy:LocationAccuracy.high);}
 Future<void> startGps()async{await gpsSub?.cancel();try{gpsSub=Geolocator.getPositionStream(locationSettings:AndroidSettings(accuracy:LocationAccuracy.high,distanceFilter:30,intervalDuration:const Duration(seconds:20),foregroundNotificationConfig:const ForegroundNotificationConfig(notificationTitle:'KRIYA360 shift tracking',notificationText:'Location sharing is active while punched in.',enableWakeLock:true))).listen((p)async{try{if(widget.user['on_shift']==true){await api.call('/gps',method:'POST',json:{'lat':p.latitude,'lng':p.longitude,'task_id':activeTask?['id']});await flushGps();}}catch(_){await queueGps(p);}});}catch(e){if(mounted)toast(context,'GPS tracking issue: $e');}}
 Map<String,dynamic>?get activeTask{for(final t in tasks){if(t['status']=='in_progress')return Map<String,dynamic>.from(t);}return null;}
 Future<void> queueGps(Position p)async{final prefs=await SharedPreferences.getInstance();final old=prefs.getStringList('pending_gps')??[];old.add(jsonEncode({'lat':p.latitude,'lng':p.longitude,'task_id':activeTask?['id']}));await prefs.setStringList('pending_gps',old.length>100?old.sublist(old.length-100):old);}
 Future<void> flushGps()async{final prefs=await SharedPreferences.getInstance();final old=prefs.getStringList('pending_gps')??[];final remaining=<String>[];for(final entry in old){try{await api.call('/gps',method:'POST',json:Map<String,dynamic>.from(jsonDecode(entry)));}catch(_){remaining.add(entry);}}await prefs.setStringList('pending_gps',remaining);}
 Future<void> punch()async{setState(()=>busy=true);try{final p=await location();final on=widget.user['on_shift']==true;final r=await api.call('/attendance/punch-${on?'out':'in'}',method:'POST',json:{'lat':p.latitude,'lng':p.longitude,'vehicle':widget.user['vehicle']??''});await widget.onUser(Map<String,dynamic>.from(r));if(on){await gpsSub?.cancel();gpsSub=null;}else{await startGps();await flushGps();}await DriverNotifications.syncShift('${widget.user['shift_expected']??'09:00'}',!on);await load();if(mounted)toast(context,on?'Punched out successfully':'Punched in successfully');}catch(e){if(mounted)toast(context,'Punch failed: $e');}finally{if(mounted)setState(()=>busy=false);}}
 Future<void> sos()async{final confirm=await showDialog<bool>(context:context,builder:(c)=>AlertDialog(icon:const Icon(Icons.sos,color:Colors.red,size:40),title:Text(tr('sos')),content:Text(tr('sosQuestion')),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:Text(tr('cancel'))),FilledButton(style:FilledButton.styleFrom(backgroundColor:Colors.red),onPressed:()=>Navigator.pop(c,true),child:Text(tr('confirm')))]));if(confirm!=true)return;try{Position? p;try{p=await location();}catch(_){ }final r=await api.call('/sos',method:'POST',json:{'confirmed':true,'lat':p?.latitude,'lng':p?.longitude,'message':'Driver requested emergency assistance'});if(mounted)toast(context,r['status']=='received_by_server'?'SOS received by management server':'SOS status unknown');}catch(e){if(mounted)showDialog(context:context,builder:(c)=>AlertDialog(title:const Text('SOS not delivered'),content:Text('Management did not confirm receipt. Call emergency services if needed. $e'),actions:[TextButton(onPressed:()=>Navigator.pop(c),child:const Text('OK'))]));}}
 Future<void> startTask(Map t)async{try{await api.call('/tasks/${t['id']}/start',method:'POST');await load();}catch(e){if(mounted)toast(context,'Could not start: $e');}}
 Future<void> navigate(Map t)async{final uri=Uri.parse('https://www.google.com/maps/dir/?api=1&destination=${t['lat']},${t['lng']}&travelmode=driving');if(!await launchUrl(uri,mode:LaunchMode.externalApplication)&&mounted)toast(context,'Unable to open navigation');}
 Future<void> sendRecipientOtp(Map t)async{
  try{
   final r=await api.call('/tasks/${t['id']}/otp/send',method:'POST');
   if(mounted)toast(context,'SMS accepted for ${r['recipient_masked']}. Ask customer for the code.');
  }catch(e){if(mounted)toast(context,'Could not send OTP: $e');}
 }
 Future<void> showRoadDirections(Map t)async{
  try{
   final data=await api.call('/tasks/${t['id']}/route');
   if(!mounted)return;
   final raw=(data['coordinates'] as List? ?? []);
   final points=<LatLng>[];
   for(final item in raw){if(item is List && item.length>=2){final lng=(item[0] as num).toDouble(),lat=(item[1] as num).toDouble();points.add(LatLng(lat,lng));}}
   if(points.isEmpty){points.add(LatLng((t['lat'] as num).toDouble(),(t['lng'] as num).toDouble()));}
   final isRoad='${data['source']??''}'.startsWith('OSRM');
   final mapController=MapController();
   await showModalBottomSheet<void>(context:context,isScrollControlled:true,showDragHandle:true,builder:(sheetContext)=>SafeArea(child:FractionallySizedBox(heightFactor:.79,child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
    Text('Delivery route • ${t['title']}',style:const TextStyle(fontSize:20,fontWeight:FontWeight.bold)),
    const SizedBox(height:6),Text('${data['distance_km']} km  •  ${data['duration_min']} min estimated'),
    const SizedBox(height:12),Expanded(child:ClipRRect(borderRadius:BorderRadius.circular(14),child:FlutterMap(mapController:mapController,options:MapOptions(initialCenter:points.first,initialZoom:11,onMapReady:(){if(points.length>1){mapController.fitCamera(CameraFit.bounds(bounds:LatLngBounds.fromPoints(points),padding:const EdgeInsets.all(28)));}}),children:[
      TileLayer(urlTemplate:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',userAgentPackageName:'com.intprosec.kriya360.driver'),
      if(points.length>1)PolylineLayer(polylines:[Polyline(points:points,strokeWidth:5,color:orange)]),
      MarkerLayer(markers:[Marker(point:points.first,width:40,height:40,child:const Icon(Icons.location_on,color:Colors.blue,size:36)),if(points.length>1)Marker(point:points.last,width:40,height:40,child:const Icon(Icons.flag,color:Colors.deepOrange,size:36))]),
      const RichAttributionWidget(attributions:[TextSourceAttribution('© OpenStreetMap contributors')]),
    ]))),
    if(!isRoad)const Padding(padding:EdgeInsets.only(top:9),child:Text('Road routing unavailable; this is not a verified driveable route.',style:TextStyle(color:Colors.red))),
    const SizedBox(height:12),SizedBox(width:double.infinity,child:FilledButton.icon(style:filled(),icon:const Icon(Icons.navigation),onPressed:()=>navigate(t),label:const Text('Open live navigation')))
   ])))));
  }catch(e){if(mounted)toast(context,'Route map unavailable: $e');}
 }
 Future<void> complete(Map t)async{final otp=TextEditingController();XFile? image;final ok=await showDialog<bool>(context:context,builder:(ctx)=>StatefulBuilder(builder:(ctx,set)=>AlertDialog(title:Text(tr('complete')),content:Column(mainAxisSize:MainAxisSize.min,children:[OutlinedButton.icon(onPressed:()=>sendRecipientOtp(t),icon:const Icon(Icons.sms_outlined),label:const Text('Send OTP to customer phone')),const SizedBox(height:10),TextField(controller:otp,keyboardType:TextInputType.number,decoration:decor(tr('otp'),Icons.password)),const SizedBox(height:14),OutlinedButton.icon(onPressed:()async{final f=await picker.pickImage(source:ImageSource.camera,imageQuality:70);if(f!=null)set(()=>image=f);},icon:const Icon(Icons.camera_alt_outlined),label:Text(image==null?tr('photo'):'Photo attached ✓')),const SizedBox(height:7),Text(tr('verify'),style:const TextStyle(fontSize:12,color:Colors.blueGrey))]),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:Text(tr('cancel'))),FilledButton(style:filled(),onPressed:()=>Navigator.pop(ctx,true),child:Text(tr('submit')))])));if(ok!=true)return;if(image==null||otp.text.trim().isEmpty){if(mounted)toast(context,'Both photo and OTP required');return;}try{await api.call('/tasks/${t['id']}/complete',method:'POST',fields:{'otp':otp.text.trim()},photo:image!.path);await load();if(mounted)toast(context,'Delivery completed and verified');}catch(e){if(mounted)toast(context,'Proof verification failed: $e');}}
 Future<void> reportLate(Map t)async{
  final reason=TextEditingController();
  final ok=await showDialog<bool>(context:context,builder:(ctx)=>AlertDialog(title:const Text('Report delivery delay'),content:Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.start,children:[Text('${t['title']}'),const SizedBox(height:14),TextField(controller:reason,maxLines:4,maxLength:600,decoration:decor('Reason for delay (minimum 5 characters)',Icons.edit_note_outlined)),const Text('Management will receive your explanation.',style:TextStyle(color:Colors.blueGrey,fontSize:12))]),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:const Text('Cancel')),FilledButton(style:filled(),onPressed:()=>Navigator.pop(ctx,true),child:const Text('Send reason'))]));
  if(ok!=true||reason.text.trim().length<5){if(ok==true&&mounted)toast(context,'Please provide a clear reason');return;}
  try{await api.call('/tasks/${t['id']}/late-reason',method:'POST',json:{'reason':reason.text.trim()});await load();if(mounted)toast(context,'Delay reason sent to management');}catch(e){if(mounted)toast(context,'Could not submit reason: $e');}
 }
 Future<void> addExpense()async{
  if(tasks.isEmpty){toast(context,'A delivery must be assigned first');return;}
  String selected=tasks.first['id'];String category='fuel';
  final amount=TextEditingController();XFile? evidence;
  final ok=await showDialog<bool>(context:context,builder:(ctx)=>StatefulBuilder(builder:(ctx,set)=>AlertDialog(
   title:Text(tr('expense')),content:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,children:[
    DropdownButtonFormField<String>(initialValue:selected,isExpanded:true,items:tasks.map<DropdownMenuItem<String>>((t)=>DropdownMenuItem(value:t['id'] as String,child:Text('${t['title']}',overflow:TextOverflow.ellipsis))).toList(),onChanged:(v)=>set(()=>selected=v!)),
    const SizedBox(height:10),DropdownButtonFormField<String>(initialValue:category,items:['fuel','toll','parking','food','other'].map((e)=>DropdownMenuItem(value:e,child:Text(e.toUpperCase()))).toList(),onChanged:(v)=>set(()=>category=v!)),
    const SizedBox(height:12),TextField(controller:amount,keyboardType:const TextInputType.numberWithOptions(decimal:true),decoration:decor(tr('amount'),Icons.currency_rupee)),
    const SizedBox(height:14),const Text('Upload payment evidence (required)',style:TextStyle(fontWeight:FontWeight.w700)),
    const SizedBox(height:8),OutlinedButton.icon(onPressed:()async{final x=await picker.pickImage(source:ImageSource.gallery,imageQuality:85);if(x!=null)set(()=>evidence=x);},icon:const Icon(Icons.upload_file),label:Text(evidence==null?'Select payment screenshot / receipt':'Evidence attached ✓')),
    TextButton.icon(onPressed:()async{final x=await picker.pickImage(source:ImageSource.camera,imageQuality:85);if(x!=null)set(()=>evidence=x);},icon:const Icon(Icons.camera_alt_outlined),label:const Text('Take receipt photo'))
   ])),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:Text(tr('cancel'))),FilledButton(style:filled(),onPressed:()=>Navigator.pop(ctx,true),child:Text(tr('submit')))])));
  if(ok!=true)return;
  final value=double.tryParse(amount.text.trim());
  if(value==null||value<=0||evidence==null){if(mounted)toast(context,'Enter a valid amount and attach payment evidence');return;}
  try{
   await api.call('/expenses/submit-evidence',method:'POST',fields:{'task_id':selected,'category':category,'amount':value.toString()},photo:evidence!.path);
   await load();if(mounted)toast(context,'Expense and evidence sent for manager review');
  }catch(e){if(mounted)toast(context,'Expense submission failed: $e');}
 }
 Future<void> licenseUpload()async{
  final photo=await picker.pickImage(source:ImageSource.gallery,imageQuality:85);
  if(photo==null)return;
  try{await api.call('/license/upload',method:'POST',photo:photo.path);await load();if(mounted)toast(context,'Licence image uploaded for manager review');}
  catch(e){if(mounted)toast(context,'Licence upload failed: $e');}
 }
 Future<void> editProfile()async{
  final name=TextEditingController(text:'${widget.user['name']??''}');
  final license=TextEditingController(text:'${widget.user['license_no']??''}');
  final phone=TextEditingController(text:'${widget.user['phone']??''}');
  final plate=TextEditingController(text:'${widget.user['vehicle_plate']??''}');
  String vehicle='${widget.user['vehicle']??''}';
  if(!['','Lorry','Truck','Heavy Truck','Container Truck'].contains(vehicle))vehicle='';
  final ok=await showDialog<String>(context:context,builder:(ctx)=>StatefulBuilder(builder:(ctx,set)=>AlertDialog(title:const Text('Edit driver profile'),content:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,children:[
   TextField(controller:name,decoration:decor('Full name',Icons.person_outline)),const SizedBox(height:10),
   TextField(controller:phone,keyboardType:TextInputType.phone,decoration:decor('Mobile number',Icons.phone_outlined)),const SizedBox(height:10),
   TextField(controller:license,decoration:decor('Driving licence number • KA0120230001234',Icons.badge_outlined)),const SizedBox(height:10),
   DropdownButtonFormField<String>(initialValue:vehicle,decoration:decor('Vehicle type',Icons.local_shipping_outlined),items:['','Lorry','Truck','Heavy Truck','Container Truck'].map((v)=>DropdownMenuItem(value:v,child:Text(v.isEmpty?'Not assigned':v))).toList(),onChanged:(v)=>set(()=>vehicle=v??'')),const SizedBox(height:10),
   TextField(controller:plate,decoration:decor('Vehicle registration',Icons.numbers)),
   const SizedBox(height:14),
   const Text('Account security',style:TextStyle(fontWeight:FontWeight.bold)),
   const SizedBox(height:6),
   OutlinedButton.icon(onPressed:()=>Navigator.pop(ctx,'pin'),icon:const Icon(Icons.lock_reset_outlined),label:const Text('Change security PIN')),
  ])),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,'cancel'),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(ctx,'save'),child:const Text('Save changes'))])));
  if(ok=='pin'){await changeSecurityPin();return;}
  if(ok!='save')return;
  try{final updated=await api.call('/me/profile',method:'PATCH',json:{'name':name.text.trim(),'phone':phone.text.trim(),'license_no':license.text.trim(),'vehicle':vehicle,'vehicle_plate':plate.text.trim()});await widget.onUser(Map<String,dynamic>.from(updated));if(mounted)toast(context,'Profile updated');}
  catch(e){if(mounted)toast(context,'Profile update failed: $e');}
 }

 Future<void> changeSecurityPin() async {
  final current=TextEditingController(),next=TextEditingController(),confirm=TextEditingController();
  bool busy=false;
  final accepted=await showDialog<bool>(context:context,builder:(dialogContext)=>StatefulBuilder(builder:(dialogContext,update)=>AlertDialog(
   title:const Text('Change security PIN'),
   content:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,children:[
    const Text('Choose a new PIN of at least 6 digits. Your current PIN is required.'),
    const SizedBox(height:14),
    TextField(controller:current,obscureText:true,keyboardType:TextInputType.number,decoration:decor('Current PIN',Icons.lock_outline)),
    const SizedBox(height:10),TextField(controller:next,obscureText:true,keyboardType:TextInputType.number,decoration:decor('New PIN (minimum 6 digits)',Icons.password)),
    const SizedBox(height:10),TextField(controller:confirm,obscureText:true,keyboardType:TextInputType.number,decoration:decor('Confirm new PIN',Icons.password)),
   ])),actions:[TextButton(onPressed:busy?null:()=>Navigator.pop(dialogContext,false),child:const Text('Cancel')),
    FilledButton(onPressed:busy?null:(){if(!RegExp(r'^\d{6,12}$').hasMatch(next.text)||next.text!=confirm.text||current.text==next.text){toast(dialogContext,'PINs must match, be 6–12 digits and differ from the old PIN');return;}Navigator.pop(dialogContext,true);},child:const Text('Update PIN'))]
  )));
  if(accepted==true){try{await api.call('/me/change-pin',method:'POST',json:{'old_pin':current.text,'new_pin':next.text});if(mounted)toast(context,'Security PIN changed successfully');}catch(e){if(mounted)toast(context,'PIN update failed: $e');}}
  current.dispose();next.dispose();confirm.dispose();
 }
 Future<void> faceEnroll()async{final consent=await showDialog<bool>(context:context,builder:(c)=>AlertDialog(title:const Text('Face image enrollment'),content:const Text('Your face photograph is sensitive personal data. It will be uploaded for restricted administrative use. This demo does not perform face matching or liveness verification. Do you consent?'),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:const Text('No')),FilledButton(onPressed:()=>Navigator.pop(c,true),child:const Text('Consent and continue'))]));if(consent!=true)return;final photo=await picker.pickImage(source:ImageSource.camera,imageQuality:75);if(photo==null)return;try{await api.call('/face/enroll',method:'POST',photo:photo.path);await load();if(mounted)toast(context,'Face photo submitted for manager review. This is not biometric identity verification.');}catch(e){if(mounted)toast(context,'Enrollment failed: $e');}}
 @override Widget build(BuildContext context) {
   final u=widget.user;
   final assigned=tasks.where((t)=>t['status']=='assigned').toList();
   final active=tasks.where((t)=>t['status']=='in_progress').toList();
   final done=tasks.where((t)=>t['status']=='completed').length;
   return Scaffold(
     appBar:AppBar(
       automaticallyImplyLeading:false,
       title:Row(children:[
         Expanded(
           child: Align(
             alignment: Alignment.centerLeft,
             child: Image.asset('assets/header_logo.png',height:46,fit:BoxFit.contain,filterQuality:FilterQuality.high),
           ),
         ),
         const SizedBox(width:6),
         Stack(children:[IconButton(tooltip:'Notifications',onPressed:showNotifications,icon:const Icon(Icons.notifications_none_rounded,color:navy)),if(notifications.where((n)=>!seenNotifications.contains('${n['id']}')).isNotEmpty)Positioned(top:7,right:7,child:Container(width:9,height:9,decoration:const BoxDecoration(color:Colors.red,shape:BoxShape.circle)))]),
         IconButton(tooltip:'Refresh',onPressed:load,icon:const Icon(Icons.refresh_rounded,color:navy))
       ]),
     ),
     body:SafeArea(child:RefreshIndicator(onRefresh:load,child:ListView(
       padding:const EdgeInsets.fromLTRB(16,14,16,24),
       children:[
         if(tab==0)...[
           modernHero(u),
           const SizedBox(height:16),
           Row(children:[
             Expanded(child:metricCard(Icons.local_shipping_outlined,'${active.length}',tr('active'),blue)),
             const SizedBox(width:10),
             Expanded(child:metricCard(Icons.assignment_outlined,'${assigned.length}',tr('assigned'),orange)),
             const SizedBox(width:10),
             Expanded(child:metricCard(Icons.check_circle_outline,'$done','Done',Colors.green)),
           ]),
           const SizedBox(height:18),
           modernShift(u),
           const SizedBox(height:22),
           responsiveSection(tr('active'),Icons.local_shipping_outlined),
           ...active.map((t)=>taskCard(t)),
           if(active.isEmpty)emptyState(Icons.route_outlined,'No active deliveries'),
           const SizedBox(height:16),
           responsiveSection(tr('assigned'),Icons.assignment_outlined),
           ...assigned.map((t)=>taskCard(t)),
           if(assigned.isEmpty)emptyState(Icons.inbox_outlined,'No deliveries assigned yet'),
         ],
         if(tab==1)...[
           responsiveSection(tr('tasks'),Icons.inventory_2_outlined),
           ...tasks.map((t)=>taskCard(t)),
           if(tasks.isEmpty)emptyState(Icons.inventory_2_outlined,'No tasks found'),
         ],

         if(tab==3)...[
           responsiveSection(tr('expenses'),Icons.receipt_long_outlined),
           SizedBox(height:52,child:FilledButton.icon(style:filled(),onPressed:addExpense,icon:const Icon(Icons.add),label:Text(tr('expense')))),
           const SizedBox(height:16),
           ...deliveryExpenseCards(),
           if(expenses.isEmpty)emptyState(Icons.receipt_long_outlined,'No expenses recorded'),
         ],
         if(tab==4)...[
           Builder(builder: (context) {
             final licenseState=licenseStatusOf(u);
             final canUpload=licenseState=='missing'||licenseState=='rejected';
             final licenseProofText=switch(licenseState){'approved'=>'Verified by manager','pending'=>'Submitted and under review','rejected'=>'Rejected — upload again required',_=>'Not uploaded'};
             return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
               Container(
                 padding:const EdgeInsets.all(20),
                 decoration:BoxDecoration(gradient:const LinearGradient(colors:[navy,Color(0xff1A518C)]),borderRadius:BorderRadius.circular(22)),
                 child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
                   Row(children:[const CircleAvatar(radius:30,backgroundColor:orange,child:Icon(Icons.person,color:Colors.white,size:32)),const SizedBox(width:15),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('${u['name']??''}',style:const TextStyle(color:Colors.white,fontWeight:FontWeight.w900,fontSize:24)),const SizedBox(height:5),Text('${u['phone']??''}',style:const TextStyle(color:Colors.white70))]))]),
                   const SizedBox(height:16),
                   statusBadge(licenseState),
                   const SizedBox(height:10),
                   Text(licenseState=='approved'?'Your licence has been verified successfully.':licenseState=='pending'?'Your licence proof is waiting for manager review.':licenseState=='rejected'?'Your previous licence proof was rejected. Upload a new one to continue verification.':'Upload your driving licence proof to complete verification.',style:const TextStyle(color:Colors.white70,height:1.35)),
                 ]),
               ),
               const SizedBox(height:18),
               panel(Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
                 const Text('Driver profile',style:TextStyle(color:navy,fontWeight:FontWeight.w900,fontSize:18)),
                 const SizedBox(height:14),
                 info(Icons.phone_outlined,'Mobile number','${u['phone']??'—'}'),
                 info(Icons.badge_outlined,'Driving licence number','${u['license_no']??'—'}'),
                 info(Icons.local_shipping_outlined,'Vehicle','${u['vehicle']??'—'}'),
                 info(Icons.confirmation_number_outlined,'Vehicle plate','${u['vehicle_plate']??'—'}'),
                 info(Icons.description_outlined,'Licence proof status',licenseProofText),
                 info(Icons.notes_outlined,'Manager note','${u['license_review_note']??'No note available'}'),
                 info(Icons.face_outlined,'Face photo',u['face_review_status']=='approved'?'Photo reviewed by manager':u['face_review_status']=='rejected'?'Photo rejected — please resubmit':u['face_enrolled']==true?'Submitted — awaiting management review':'Not enrolled'),
                 const SizedBox(height:14),
                 FilledButton.icon(style:filled(),onPressed:editProfile,icon:const Icon(Icons.edit_outlined),label:const Text('Edit profile & security PIN')),
                 if(u['face_enrolled']!=true||u['face_review_status']=='rejected')...[ 
                   const SizedBox(height:12),
                   OutlinedButton.icon(onPressed:faceEnroll,icon:const Icon(Icons.face_outlined),label:Text(u['face_review_status']=='rejected'?'Resubmit face photo':'Enroll face photo')),
                 ],
                 if(u['face_review_status']=='pending')const Padding(padding:EdgeInsets.only(top:9),child:Text('Your face photo is awaiting management review.',style:TextStyle(fontSize:12,color:Colors.blueGrey))),
                 if(canUpload)...[
                   const SizedBox(height:12),
                   OutlinedButton.icon(onPressed:licenseUpload,icon:const Icon(Icons.upload_file),label:Text(licenseState=='rejected'?'Re-upload rejected licence proof':'Upload driving licence proof')),
                   const SizedBox(height:8),
                   Text(licenseState=='rejected'?'Your licence proof was rejected. Please submit a corrected image for another review.':'Upload your licence evidence to complete verification.',style:const TextStyle(color:Colors.blueGrey,height:1.35)),
                 ],
               ])),
               panel(Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[const Text('Preferences & account',style:TextStyle(color:navy,fontWeight:FontWeight.w900,fontSize:17)),const SizedBox(height:10),Text(tr('language'),style:const TextStyle(fontWeight:FontWeight.bold)),DropdownButton<String>(isExpanded:true,value:widget.lang,items:const[DropdownMenuItem(value:'en',child:Text('English')),DropdownMenuItem(value:'hi',child:Text('हिन्दी')),DropdownMenuItem(value:'kn',child:Text('ಕನ್ನಡ')),DropdownMenuItem(value:'ta',child:Text('தமிழ்')),DropdownMenuItem(value:'te',child:Text('తెలుగు'))],onChanged:(v){if(v!=null)widget.onLanguage(v);}),const SizedBox(height:12),OutlinedButton.icon(onPressed:widget.onLogout,icon:const Icon(Icons.logout),label:Text(tr('signOut')))])),
               const SizedBox(height:22),
               const Center(child:BrandCompanyFooter(logoHeight:42)),
             ]);
           }),
         ],
       ],
     ))),
     bottomNavigationBar:NavigationBar(
       height:76,
       labelBehavior:NavigationDestinationLabelBehavior.alwaysShow,
       selectedIndex:tab,
       onDestinationSelected:(v){if(v==2){sos();return;}setState(()=>tab=v);},
       indicatorColor:const Color(0xffffeadb),
       destinations:[
         NavigationDestination(icon:const Icon(Icons.home_outlined),selectedIcon:const Icon(Icons.home_rounded,color:orange),label:tr('home')),
         NavigationDestination(icon:const Icon(Icons.assignment_outlined),selectedIcon:const Icon(Icons.assignment_rounded,color:orange),label:tr('tasks')),
         NavigationDestination(icon:const KriyaSosNavIcon(),selectedIcon:const KriyaSosNavIcon(),label:'SOS'),
         NavigationDestination(icon:const Icon(Icons.receipt_long_outlined),selectedIcon:const Icon(Icons.receipt_long,color:orange),label:tr('expenses')),
         NavigationDestination(icon:const Icon(Icons.person_outline),selectedIcon:const Icon(Icons.person,color:orange),label:tr('profile')),
       ],
     ),
   );
 }
 Widget modernHero(Map<String,dynamic> u)=>Container(
   padding:const EdgeInsets.all(22),
   decoration:BoxDecoration(gradient:const LinearGradient(begin:Alignment.topLeft,end:Alignment.bottomRight,colors:[navy,Color(0xff19518B)]),borderRadius:BorderRadius.circular(24)),
   child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
     Row(children:[const Icon(Icons.local_shipping_outlined,color:orange,size:22),const SizedBox(width:9),const Expanded(child:Text('KRIYA360 DRIVER',style:TextStyle(color:Colors.white70,fontWeight:FontWeight.w700,letterSpacing:2,fontSize:11)))]),
     const SizedBox(height:18),
     Text('Welcome back,',style:TextStyle(color:Colors.white.withValues(alpha:.8),fontSize:15)),
     const SizedBox(height:4),
     Text('${u['name']??'Driver'}',maxLines:2,overflow:TextOverflow.ellipsis,style:const TextStyle(fontSize:28,color:Colors.white,fontWeight:FontWeight.w900)),
     const SizedBox(height:18),
     Row(children:[Icon(u['on_shift']==true?Icons.check_circle:Icons.pause_circle_outline,color:u['on_shift']==true?Colors.lightGreenAccent:Colors.white70,size:17),const SizedBox(width:7),Expanded(child:Text(u['on_shift']==true?tr('onShift'):tr('offShift'),softWrap:true,style:const TextStyle(color:Colors.white,fontSize:13)))])
   ]),
 );
 Widget metricCard(IconData icon,String value,String label,Color color)=>Container(
   constraints:const BoxConstraints(minHeight:112),padding:const EdgeInsets.symmetric(horizontal:9,vertical:13),
   decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(17),border:Border.all(color:const Color(0xffE1E9F2))),
   child:Column(mainAxisAlignment:MainAxisAlignment.center,children:[Icon(icon,color:color,size:21),const SizedBox(height:6),Text(value,style:const TextStyle(color:navy,fontSize:22,fontWeight:FontWeight.w900)),const SizedBox(height:3),Text(label,maxLines:2,overflow:TextOverflow.ellipsis,textAlign:TextAlign.center,style:const TextStyle(fontSize:10,color:Colors.blueGrey,fontWeight:FontWeight.w600))]),
 );
 Widget modernShift(Map<String,dynamic>u)=>Container(
   padding:const EdgeInsets.all(16),
   decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(20),border:Border.all(color:const Color(0xffE1E9F2))),
   child:LayoutBuilder(builder:(context,c){
     final details=Row(children:[const Icon(Icons.access_time_rounded,color:blue,size:28),const SizedBox(width:12),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
       Text(tr('attendance'),maxLines:2,overflow:TextOverflow.ellipsis,style:const TextStyle(color:navy,fontSize:16,fontWeight:FontWeight.w800)),
       const SizedBox(height:3),Text(u['on_shift']==true?tr('onShift'):tr('offShift'),softWrap:true,style:const TextStyle(color:Colors.blueGrey,fontSize:12))
     ]))]);
     final btn=FilledButton(onPressed:busy?null:punch,style:filled(),child:Padding(padding:const EdgeInsets.symmetric(vertical:13),child:Text(u['on_shift']==true?tr('punchOut'):tr('punchIn'),textAlign:TextAlign.center)));
     return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[details,const SizedBox(height:14),btn]);
   }),
 );
 Widget responsiveSection(String heading,IconData icon)=>Padding(
   padding:const EdgeInsets.only(bottom:12),
   child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[Icon(icon,color:orange,size:23),const SizedBox(width:10),Expanded(child:Text(heading,softWrap:true,style:const TextStyle(color:navy,fontSize:19,fontWeight:FontWeight.w800)))]),
 );
 Widget emptyState(IconData icon,String message)=>Container(
   margin:const EdgeInsets.only(bottom:12),padding:const EdgeInsets.symmetric(vertical:27,horizontal:12),
   decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(18),border:Border.all(color:const Color(0xffE1E9F2))),
   child:Column(children:[Icon(icon,color:Colors.blueGrey.shade300,size:31),const SizedBox(height:10),Text(message,textAlign:TextAlign.center,style:const TextStyle(color:Colors.blueGrey))]),
 );
 Widget emergencyPanel()=>Container(
   padding:const EdgeInsets.all(22),
   decoration:BoxDecoration(color:const Color(0xfffff3f4),border:Border.all(color:const Color(0xffF6C6CB)),borderRadius:BorderRadius.circular(22)),
   child:Column(children:[
     const Icon(Icons.health_and_safety_rounded,size:55,color:Color(0xffD83343)),
     const SizedBox(height:12),Text(tr('sos'),textAlign:TextAlign.center,style:const TextStyle(fontSize:21,fontWeight:FontWeight.w800,color:navy)),
     const SizedBox(height:10),Text(tr('sosQuestion'),textAlign:TextAlign.center,style:const TextStyle(color:Colors.blueGrey,fontSize:14)),
     const SizedBox(height:22),sosButton(),
     const SizedBox(height:10),const Text('SOS is sent only after you confirm. If the alert fails, call emergency services directly.',textAlign:TextAlign.center,style:TextStyle(color:Colors.blueGrey,fontSize:12))
   ]),
 );
 List<Widget> deliveryExpenseCards(){
   final grouped=<String,List<Map<String,dynamic>>>{};
   for(final raw in expenses){final e=Map<String,dynamic>.from(raw as Map);final id='${e['task_id']??'unassigned'}';grouped.putIfAbsent(id,()=>[]).add(e);}
   final result=<Widget>[];
   for(final entry in grouped.entries){
     final related=tasks.where((t)=>'${t['id']}'==entry.key);
     final task=related.isNotEmpty?related.first:null;
     final name=task==null?'Delivery ${entry.key.length>8?entry.key.substring(0,8):entry.key}':'${task['title']}';
     final amount=entry.value.fold<double>(0,(sum,e)=>sum+(double.tryParse('${e['amount']}')??0));
     final pending=entry.value.where((e)=>e['status']=='pending').length;
     result.add(Card(margin:const EdgeInsets.only(bottom:14),clipBehavior:Clip.antiAlias,shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(17),side:const BorderSide(color:Color(0xffE0E8F2))),child:ExpansionTile(
       tilePadding:const EdgeInsets.symmetric(horizontal:14,vertical:8),childrenPadding:const EdgeInsets.fromLTRB(14,0,14,14),
       leading:const CircleAvatar(backgroundColor:Color(0xffE6F0FD),child:Icon(Icons.local_shipping_outlined,color:blue)),
       title:Text(name,maxLines:2,overflow:TextOverflow.ellipsis,style:const TextStyle(color:navy,fontWeight:FontWeight.w800,fontSize:15)),
       subtitle:Text('${entry.value.length} expense${entry.value.length==1?'':'s'}  •  ${pending==0?'All reviewed':'$pending pending'}',style:const TextStyle(fontSize:12,color:Colors.blueGrey)),
       trailing:Column(mainAxisSize:MainAxisSize.min,mainAxisAlignment:MainAxisAlignment.center,children:[Text('₹${amount.toStringAsFixed(2)}',style:const TextStyle(color:navy,fontWeight:FontWeight.w900,fontSize:15)),const Icon(Icons.expand_more,color:blue,size:18)]),
       showTrailingIcon:false,
       children:[const Divider(height:12),...entry.value.asMap().entries.map((item)=>Padding(padding:const EdgeInsets.symmetric(vertical:6),child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[
         CircleAvatar(radius:13,backgroundColor:const Color(0xffEFF4FB),child:Text('${item.key+1}',style:const TextStyle(color:blue,fontSize:11,fontWeight:FontWeight.bold))),
         const SizedBox(width:10),Expanded(child:expenseCard(item.value)),
       ]))),],
     )));
   }
   return result;
 }
 Widget expenseCard(Map e){
   final status='${e['status']??'pending'}'.toLowerCase();
   final color=status=='approved'?const Color(0xff168451):status=='rejected'?const Color(0xffC12A3A):const Color(0xffB66B08);
   final shade=status=='approved'?const Color(0xffE8F8EF):status=='rejected'?const Color(0xffFEECEF):const Color(0xffFFF3DF);
   return panel(Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
     Row(children:[const Icon(Icons.receipt_long,color:blue),const SizedBox(width:9),Expanded(child:Text('${e['category']??''}'.toUpperCase(),style:const TextStyle(color:navy,fontWeight:FontWeight.w800))),Text('₹${e['amount']}',style:const TextStyle(color:navy,fontWeight:FontWeight.w900,fontSize:18))]),
     if(e['receipt_url']!=null)...[const SizedBox(height:10),const Row(children:[Icon(Icons.verified_outlined,color:blue,size:16),SizedBox(width:6),Text('Payment evidence uploaded',style:TextStyle(color:Colors.blueGrey))])],
     if((e['fraud_flags'] as List? ?? []).isNotEmpty)...[const SizedBox(height:8),const Text('Flagged for manager verification',style:TextStyle(color:Color(0xffB66B08)))],
     const SizedBox(height:14),Align(alignment:Alignment.centerLeft,child:Container(padding:const EdgeInsets.symmetric(horizontal:12,vertical:7),decoration:BoxDecoration(color:shade,borderRadius:BorderRadius.circular(30)),child:Row(mainAxisSize:MainAxisSize.min,children:[Icon(status=='approved'?Icons.check_circle:status=='rejected'?Icons.cancel:Icons.schedule,color:color,size:16),const SizedBox(width:6),Text(status.toUpperCase(),style:TextStyle(color:color,fontSize:11,fontWeight:FontWeight.w800))])))
   ]));
 }

 Widget topCard(Map<String,dynamic> u)=>Container(padding:const EdgeInsets.all(22),decoration:BoxDecoration(gradient:const LinearGradient(colors:[navy,Color(0xff15487f)]),borderRadius:BorderRadius.circular(18)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('KRIYA360 DRIVER',style:TextStyle(letterSpacing:2,fontSize:10,color:Color(0xffacc9eb),fontWeight:FontWeight.bold)),const SizedBox(height:12),Text('${tr('hello')},',style:const TextStyle(color:Colors.white70)),Text(u['name']??'',style:const TextStyle(color:Colors.white,fontWeight:FontWeight.w900,fontSize:25)),const SizedBox(height:15),Row(children:[const Icon(Icons.location_on,color:orange,size:17),const SizedBox(width:6),Text(u['on_shift']==true?tr('onShift'):tr('offShift'),style:const TextStyle(color:Colors.white))])]));
 Widget shiftCard(Map<String, dynamic> u) => panel(
  Row(
    children: [
      Icon(
        u['on_shift'] == true ? Icons.timer_outlined : Icons.access_time,
        color: blue,
        size: 31,
      ),
      const SizedBox(width: 12),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(tr('attendance'), style: const TextStyle(fontWeight: FontWeight.w800)),
            Text(
              u['on_shift'] == true ? tr('onShift') : tr('offShift'),
              style: const TextStyle(fontSize: 12, color: Colors.blueGrey),
            ),
          ],
        ),
      ),
      FilledButton(
        style: filled(),
        onPressed: busy ? null : punch,
        child: Text(u['on_shift'] == true ? tr('punchOut') : tr('punchIn')),
      ),
    ],
  ),
 );
 Widget section(String title,IconData icon)=>Padding(padding:const EdgeInsets.only(bottom:12),child:Row(children:[Icon(icon,color:orange),const SizedBox(width:9),Text(title,style:const TextStyle(fontSize:19,fontWeight:FontWeight.w900,color:navy))]));
 Widget taskCard(Map t)=>Container(
   margin:const EdgeInsets.only(bottom:13),padding:const EdgeInsets.all(17),
   decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(19),border:Border.all(color:const Color(0xffE1E9F2))),
   child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
     Row(crossAxisAlignment:CrossAxisAlignment.start,children:[
       Container(padding:const EdgeInsets.all(9),decoration:BoxDecoration(color:const Color(0xffEAF3FF),borderRadius:BorderRadius.circular(10)),child:const Icon(Icons.local_shipping_outlined,color:blue)),
       const SizedBox(width:10),
       Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
         Text('${t['title']??''}',softWrap:true,style:const TextStyle(fontWeight:FontWeight.w900,fontSize:16,color:navy)),
         const SizedBox(height:6),badge('${t['status']??''}'),
       ])),
     ]),
     const SizedBox(height:14),
     info(Icons.location_on_outlined,'Destination','${t['address']??''}'),
     info(Icons.schedule_outlined,'Due','${t['due_at']?.toString().replaceFirst('T',' ').substring(0,16)??'—'}'),
     info(Icons.route_outlined,'Route','${t['route_distance_km']??0} km · ${t['route_duration_min']??0} min'),
     if((t['late_reason']??'').toString().isNotEmpty)info(Icons.info_outline,'Reported delay','${t['late_reason']}'),
     if('${t['route_source']??''}'.contains('fallback'))const Padding(padding:EdgeInsets.only(top:5),child:Text('Route is an estimate, not turn-by-turn navigation',style:TextStyle(color:Colors.deepOrange,fontSize:11))),
     const Divider(height:25),
     Wrap(spacing:8,runSpacing:8,children:[
       if(t['status']=='assigned')FilledButton.icon(style:filled(),onPressed:()=>startTask(t),icon:const Icon(Icons.play_arrow),label:Text(tr('start'))),
       if(t['status']=='in_progress')FilledButton.icon(style:filled(),onPressed:()=>complete(t),icon:const Icon(Icons.verified_outlined),label:Text(tr('complete'))),
       if(t['status']!='completed')OutlinedButton.icon(onPressed:()=>showRoadDirections(t),icon:const Icon(Icons.route_outlined),label:const Text('View route map')),
       if(t['status']!='completed')OutlinedButton.icon(onPressed:()=>navigate(t),icon:const Icon(Icons.navigation_outlined),label:Text(tr('navigate'))),
       if(t['status']!='completed'&&t['status']!='cancelled')OutlinedButton.icon(onPressed:()=>reportLate(t),icon:const Icon(Icons.schedule_send_outlined),label:const Text('Report delay')),
       if(t['status']=='completed')const Chip(avatar:Icon(Icons.check_circle,color:Colors.green,size:18),label:Text('OTP verified',style:TextStyle(fontSize:11))),
     ]),
   ]),
 );

 Widget sosButton()=>SizedBox(width:double.infinity,height:58,child:FilledButton.icon(style:FilledButton.styleFrom(backgroundColor:const Color(0xffD83343),shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(13))),onPressed:sos,icon:const Icon(Icons.sos,size:29),label:Text(tr('sos'),style:const TextStyle(fontWeight:FontWeight.w900,fontSize:16))));
 Widget panel(Widget child)=>Container(margin:const EdgeInsets.only(bottom:12),padding:const EdgeInsets.all(17),decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(15),border:Border.all(color:const Color(0xffe6edf5))),child:child);
 Widget hint(String s)=>Padding(padding:const EdgeInsets.symmetric(vertical:24),child:Center(child:Text(s,style:const TextStyle(color:Colors.blueGrey))));
 Widget badge(String s)=>Container(padding:const EdgeInsets.symmetric(horizontal:9,vertical:6),decoration:BoxDecoration(color:s=='completed'?const Color(0xffe6f7ee):const Color(0xfffff1e3),borderRadius:BorderRadius.circular(8)),child:Text(s.toUpperCase().replaceAll('_',' '),style:TextStyle(color:s=='completed'?Colors.green:orange,fontSize:10,fontWeight:FontWeight.bold)));
 Widget info(IconData icon,String k,String v)=>Padding(padding:const EdgeInsets.symmetric(vertical:6),child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[Icon(icon,size:18,color:blue),const SizedBox(width:8),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(k,style:const TextStyle(color:Colors.blueGrey,fontSize:11)),Text(v,style:const TextStyle(color:navy,fontSize:13,fontWeight:FontWeight.w700))]))]));
}
