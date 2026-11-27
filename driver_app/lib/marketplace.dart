/// KRIYA360 merchant pilot. Uses the existing Flutter packages and Android app.
/// Merchant credentials are isolated from the existing driver session.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:geolocator/geolocator.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart' as gm;
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart' as ll;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

const _navy = Color(0xff081F45);
const _orange = Color(0xffF47A20);
const _bg = Color(0xffF4F7FB);
const marketplaceUiEnabled = bool.fromEnvironment('KRIYA_MERCHANT_ENABLED', defaultValue: true);
const _googleMaps = bool.fromEnvironment('KRIYA_GOOGLE_MAPS_ENABLED', defaultValue: false);
const _merchantSession = 'kriya_merchant_token_v1';
const _storage = FlutterSecureStorage();

typedef MarketCall = Future<dynamic> Function(String path, String method, Map<String, dynamic>? body);

class MarketFailure implements Exception {
  final String message;
  final int? status;
  const MarketFailure(this.message, [this.status]);
  @override
  String toString() => message;
}

String _message(Object error) {
  if (error is MarketFailure) return error.message;
  if (error is TimeoutException || error is SocketException || error is http.ClientException) {
    return 'Unable to connect. Check your internet connection and try again.';
  }
  // Do not surface a raw exception, endpoint, token or stack trace to users.
  return 'Unable to complete this action. Please try again.';
}

class _MerchantApi {
  final String origin;
  String? token;
  _MerchantApi(String url) : origin = url.replaceFirst(RegExp(r'/+$'), '');
  Future<dynamic> call(String path, String method, Map<String, dynamic>? data) async {
    final client = http.Client();
    try {
      final r = http.Request(method, Uri.parse('$origin/api$path'));
      r.followRedirects = false;
      r.headers['Accept'] = 'application/json';
      if (token != null) r.headers['Authorization'] = 'Bearer $token';
      if (data != null) {
        r.headers['Content-Type'] = 'application/json';
        r.body = jsonEncode(data);
      }
      final response = await http.Response.fromStream(await client.send(r).timeout(const Duration(seconds: 40))).timeout(const Duration(seconds: 40));
      dynamic result;
      try { result = jsonDecode(response.body); } catch (_) { result = null; }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final code = response.statusCode;
        final detail = result is Map ? result['detail'] : null;
        throw MarketFailure(code >= 500 ? 'Service temporarily unavailable or not yet configured. Please try again.' : code == 429 ? 'Too many requests. Try again shortly.' : detail is String ? detail : 'Check the details and try again.', code);
      }
      if (result == null) throw const MarketFailure('Unexpected server response. Please try again.');
      return result;
    } on TimeoutException {
      throw const MarketFailure('Connection timed out. Refresh before retrying.');
    } on SocketException {
      throw const MarketFailure('Unable to connect. Check your internet connection.');
    } on http.ClientException {
      throw const MarketFailure('Unable to connect. Check your internet connection.');
    } finally { client.close(); }
  }
}

List<Map<String, dynamic>> _rows(dynamic raw) => (raw as List).map((x) => Map<String, dynamic>.from(x as Map)).toList();
Map<String, dynamic> _object(dynamic raw) => Map<String, dynamic>.from(raw as Map);
String _stateText(dynamic state) => (state ?? '').toString().replaceAll('_', ' ');
String _text(dynamic x) => x == null ? '' : x.toString();
String _key() => List.generate(24, (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0')).join();
ButtonStyle _primary() => FilledButton.styleFrom(backgroundColor: _orange, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16));
Widget _spin() => const SizedBox(width: 19, height: 19, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white));
void _notice(BuildContext context, String value) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value), behavior: SnackBarBehavior.floating));
}

class _ErrorCard extends StatelessWidget {
  final String message;
  final VoidCallback? retry;
  const _ErrorCard(this.message, {this.retry});
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(14), child: Row(children: [const Icon(Icons.info_outline, color: Colors.deepOrange), const SizedBox(width: 10), Expanded(child: Text(message)), if (retry != null) TextButton(onPressed: retry, child: const Text('Retry'))])));
}

Widget _field(TextEditingController controller, String title, {TextInputType? type, bool required = true, bool obscure = false, Widget? suffix, int maxLines = 1}) => Padding(
  padding: const EdgeInsets.only(bottom: 12),
  child: TextFormField(controller: controller, keyboardType: type, obscureText: obscure, maxLines: maxLines, decoration: InputDecoration(labelText: title, filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)), suffixIcon: suffix), validator: required ? (value) => (value == null || value.trim().isEmpty) ? 'Required' : null : null));

/// Introduction screens use built-in vector icons, not large assets or extra SDKs.
class RoleGateway extends StatelessWidget {
  final VoidCallback onDriver;
  final String apiOrigin;
  const RoleGateway({super.key, required this.onDriver, required this.apiOrigin});
  Future<void> _choose(BuildContext context, bool merchant) async {
    final prefs = await SharedPreferences.getInstance();
    final key = merchant ? 'kriya_merchant_intro_seen' : 'kriya_driver_intro_seen';
    if (!context.mounted) return;
    if (prefs.getBool(key) != true) {
      final finished = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => _IntroPage(merchant: merchant)));
      if (finished != true) return;
      await prefs.setBool(key, true);
    }
    if (!context.mounted) return;
    if (merchant) {
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => MerchantScreen(apiOrigin: apiOrigin)));
    } else { onDriver(); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(backgroundColor: Colors.white, body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 460), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    Image.asset('assets/signin_logo.png', height: 105, fit: BoxFit.contain),
    const SizedBox(height: 28),
    Text('Connect. Collect. Deliver.', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: _navy, fontWeight: FontWeight.w800)),
    const SizedBox(height: 9), const Text('Choose how you use KRIYA360.', style: TextStyle(color: Colors.blueGrey)), const SizedBox(height: 20),
    _roleCard(context, Icons.local_shipping_outlined, 'I’m a driver', 'Manage shifts, assignments, merchant pickups and deliveries.', () => _choose(context, false)),
    if (marketplaceUiEnabled) _roleCard(context, Icons.storefront_outlined, 'I’m a merchant', 'Find nearby drivers and arrange package collection and delivery.', () => _choose(context, true)),
    TextButton(onPressed: onDriver, child: const Text('Already a driver? Sign in')),
    const SizedBox(height: 24), Center(child: Image.asset('assets/company_logo.png', width: 150, height: 54, fit: BoxFit.contain, semanticLabel: 'IntProSec company logo')),
  ]))))));
  Widget _roleCard(BuildContext context, IconData icon, String title, String description, VoidCallback action) => Card(elevation: 0, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: const BorderSide(color: Color(0xffdfe6ef))), child: InkWell(borderRadius: BorderRadius.circular(18), onTap: action, child: Padding(padding: const EdgeInsets.all(18), child: Row(children: [Container(width: 58, height: 58, decoration: BoxDecoration(color: _orange.withValues(alpha: .1), borderRadius: BorderRadius.circular(16)), child: Icon(icon, color: _orange, size: 30)), const SizedBox(width: 14), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: _navy)), const SizedBox(height: 5), Text(description, style: const TextStyle(color: Colors.blueGrey))])), const Icon(Icons.chevron_right)]))));
}

class _IntroPage extends StatefulWidget {
  final bool merchant;
  const _IntroPage({required this.merchant});
  @override
  State<_IntroPage> createState() => _IntroPageState();
}
class _IntroPageState extends State<_IntroPage> {
  final _pages = PageController();
  int _index = 0;
  @override
  void dispose() { _pages.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    final items = widget.merchant ? <(IconData, String, String)>[
      (Icons.storefront, 'Grow your business', 'Manage pickups for your shop or independent online business.'),
      (Icons.link, 'Connect your store', 'Link a supported Shopify store after merchant approval, or create delivery requests manually.'),
      (Icons.local_shipping, 'Find a nearby driver', 'Choose an eligible available driver and communicate securely.'),
      (Icons.location_on, 'Track your deliveries', 'Follow pickup, transit and verified delivery progress.')
    ] : <(IconData, String, String)>[
      (Icons.waving_hand, 'Welcome to KRIYA360', 'Your companion for field operations, attendance and deliveries.'),
      (Icons.route, 'Drive smarter', 'Use navigation, live location and task routes during your shift.'),
      (Icons.inventory_2, 'Connect and collect', 'Choose to appear in merchant discovery and receive pickup requests.'),
      (Icons.verified_user, 'Deliver with confidence', 'Confirm handover securely and report problems or emergencies.')
    ];
    return Scaffold(backgroundColor: Colors.white, appBar: AppBar(backgroundColor: Colors.white, actions: [TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Skip'))]), body: SafeArea(child: Column(children: [Expanded(child: PageView.builder(controller: _pages, itemCount: items.length, onPageChanged: (i) => setState(() => _index = i), itemBuilder: (context, index) { final item=items[index]; return Padding(padding: const EdgeInsets.all(28), child: Center(child: SingleChildScrollView(child: Column(children: [Container(width: 175, height: 175, decoration: BoxDecoration(color: _orange.withValues(alpha: .09), shape: BoxShape.circle), child: Icon(item.$1, size: 88, color: _orange)), const SizedBox(height: 40), Text(item.$2, textAlign: TextAlign.center, style: const TextStyle(fontSize: 29, color: _navy, fontWeight: FontWeight.w900)), const SizedBox(height: 14), Text(item.$3, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, color: Colors.blueGrey))])))); })), Padding(padding: const EdgeInsets.all(24), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Row(mainAxisAlignment: MainAxisAlignment.center, children: List.generate(items.length, (i) => AnimatedContainer(duration: const Duration(milliseconds: 180), margin: const EdgeInsets.symmetric(horizontal: 4), height: 8, width: i == _index ? 24 : 8, decoration: BoxDecoration(color: i == _index ? _orange : Colors.black12, borderRadius: BorderRadius.circular(8))))), const SizedBox(height: 22), FilledButton(style: _primary(), onPressed: () { if (_index == items.length-1) { Navigator.pop(context, true); } else { _pages.nextPage(duration: const Duration(milliseconds: 250), curve: Curves.easeOut); } }, child: Text(_index == items.length-1 ? 'Get started' : 'Continue'))]))])));
  }
}

Future<Position> _gps() async {
  if (!await Geolocator.isLocationServiceEnabled()) throw const MarketFailure('Turn on location services to continue.');
  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
  if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) throw const MarketFailure('Location permission is required. Enable it in Settings or choose a pin manually.');
  return Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 20)));
}

/// Map uses the application's existing provider switch. Coordinates are explicit.
class _MarketMap extends StatelessWidget {
  final ll.LatLng center;
  final List<(ll.LatLng, String)> pins;
  final ValueChanged<ll.LatLng>? onPick;
  const _MarketMap({super.key, required this.center, required this.pins, this.onPick});
  @override
  Widget build(BuildContext context) {
    if (_googleMaps && Platform.isAndroid) {
      return gm.GoogleMap(initialCameraPosition: gm.CameraPosition(target: gm.LatLng(center.latitude,center.longitude),zoom: 13), markers: {for (var i=0;i<pins.length;i++) gm.Marker(markerId: gm.MarkerId('$i'), position: gm.LatLng(pins[i].$1.latitude,pins[i].$1.longitude), infoWindow: gm.InfoWindow(title:pins[i].$2))}, onTap:onPick == null ? null : (p)=>onPick!(ll.LatLng(p.latitude,p.longitude)), myLocationEnabled:false, myLocationButtonEnabled:false);
    }
    return FlutterMap(options: MapOptions(initialCenter: center, initialZoom: 13, onTap: onPick == null ? null : (_,p)=>onPick!(p)), children: [TileLayer(urlTemplate:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',userAgentPackageName:'com.example.kriya360_driver'), MarkerLayer(markers:[for(final p in pins) Marker(point:p.$1,width:38,height:38,child:Tooltip(message:p.$2,child:const Icon(Icons.location_on,color:_orange,size:36)))]), const RichAttributionWidget(attributions:[TextSourceAttribution('OpenStreetMap contributors')])]);
  }
}

class _PinPicker extends StatefulWidget {
  final ll.LatLng start;
  const _PinPicker({required this.start});
  @override
  State<_PinPicker> createState()=>_PinPickerState();
}
class _PinPickerState extends State<_PinPicker> {
  late ll.LatLng point=widget.start;
  @override
  Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Choose location')),body:Column(children:[Expanded(child:_MarketMap(center:widget.start,pins:[(point,'Selected location')],onPick:(p)=>setState(()=>point=p))), Padding(padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[const Text('Tap the map to place your pin.'),Text('${point.latitude.toStringAsFixed(5)}, ${point.longitude.toStringAsFixed(5)}'),const SizedBox(height:10),FilledButton(style:_primary(),onPressed:()=>Navigator.pop(context,point),child:const Text('Use this location'))]))]));
}

class _LocationFields extends StatefulWidget {
  final TextEditingController address, lat, lng;
  final String label;
  const _LocationFields({required this.address,required this.lat,required this.lng,required this.label});
  @override
  State<_LocationFields> createState()=>_LocationFieldsState();
}
class _LocationFieldsState extends State<_LocationFields> {
  bool _busy=false;
  void _set(ll.LatLng p){widget.lat.text=p.latitude.toStringAsFixed(6);widget.lng.text=p.longitude.toStringAsFixed(6);}
  Future<void> _locate() async {
    setState(()=>_busy=true);
    try { final p=await _gps();if(mounted)_set(ll.LatLng(p.latitude,p.longitude)); } catch(e){if(mounted)_notice(context,_message(e));}
    finally {if(mounted)setState(()=>_busy=false);}
  }
  Future<void> _pick() async {
    final a=double.tryParse(widget.lat.text),b=double.tryParse(widget.lng.text);
    final start=a!=null&&b!=null&&a.isFinite&&b.isFinite&&a.abs()<=90&&b.abs()<=180?ll.LatLng(a,b):const ll.LatLng(12.9716,77.5946);
    final result=await Navigator.of(context).push<ll.LatLng>(MaterialPageRoute(builder:(_)=>_PinPicker(start:start)));
    if(mounted&&result!=null)_set(result);
  }
  @override
  Widget build(BuildContext context)=>Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[_field(widget.address,'${widget.label} address',maxLines:2),Row(children:[Expanded(child:OutlinedButton.icon(onPressed:_busy?null:_locate,icon:const Icon(Icons.my_location),label:Text(_busy?'Locating…':'Use GPS'))),const SizedBox(width:8),Expanded(child:OutlinedButton.icon(onPressed:_busy?null:_pick,icon:const Icon(Icons.map_outlined),label:const Text('Map pin')))]),const SizedBox(height:10),Row(children:[Expanded(child:_field(widget.lat,'Latitude',type:const TextInputType.numberWithOptions(decimal:true,signed:true))),const SizedBox(width:8),Expanded(child:_field(widget.lng,'Longitude',type:const TextInputType.numberWithOptions(decimal:true,signed:true)))])]);
}

ll.LatLng _checkedPin(TextEditingController lat,TextEditingController lng) {
  final a=double.tryParse(lat.text.trim()),b=double.tryParse(lng.text.trim());
  if(a==null||b==null||!a.isFinite||!b.isFinite||a.abs()>90||b.abs()>180)throw const MarketFailure('Choose a valid map location.');
  return ll.LatLng(a,b);
}

class MerchantScreen extends StatefulWidget {
  final String apiOrigin;
  const MerchantScreen({super.key,required this.apiOrigin});
  @override
  State<MerchantScreen> createState()=>_MerchantScreenState();
}
class _MerchantScreenState extends State<MerchantScreen> {
  late final _MerchantApi _api=_MerchantApi(widget.apiOrigin);
  Map<String,dynamic>? _merchant;
  bool _loading=true;
  String? _error;
  @override
  void initState(){super.initState();_restore();}
  Future<void> _restore()async{
    if(mounted)setState((){_loading=true;_error=null;});
    try{
      _api.token=await _storage.read(key:_merchantSession);
      if(_api.token!=null){_merchant=_object(await _api.call('/marketplace/me','GET',null));}
    }on MarketFailure catch(e){if(e.status==401){await _storage.delete(key:_merchantSession);_api.token=null;_merchant=null;}else{_error=e.message;}}
    catch(e){_error=_message(e);}
    finally{if(mounted)setState(()=>_loading=false);}
  }
  Future<void> _auth(String path,Map<String,dynamic> body)async{
    final result=_object(await _api.call(path,'POST',body));
    final token=result['access_token'] as String;
    await _storage.write(key:_merchantSession,value:token);_api.token=token;
    if(mounted)setState(()=>_merchant=_object(result['merchant']));
  }
  Future<dynamic> _authorizedCall(String path,String method,Map<String,dynamic>? data) async {
    try{return await _api.call(path,method,data);}on MarketFailure catch(e){
      if(e.status==401){await _storage.delete(key:_merchantSession);_api.token=null;if(mounted)setState((){_merchant=null;_error=null;});}
      rethrow;
    }
  }
  Future<void> _logout()async{
    // A server outage must not prevent local sign-out.
    try{await _api.call('/marketplace/auth/logout','POST',null);}catch(_){}
    await _storage.delete(key:_merchantSession);_api.token=null;
    if(mounted)setState((){_merchant=null;_error=null;});
  }
  @override
  Widget build(BuildContext context){
    if(_loading)return const Scaffold(body:Center(child:CircularProgressIndicator()));
    if(_error!=null)return Scaffold(appBar:AppBar(title:const Text('Merchant')),body:Center(child:Padding(padding:const EdgeInsets.all(20),child:_ErrorCard(_error!,retry:_restore))));
    final m=_merchant;
    if(m==null)return _MerchantAuth(onAuth:_auth);
    if(m['state']!='approved')return Scaffold(appBar:AppBar(title:const Text('Merchant verification')),body:Center(child:SingleChildScrollView(padding:const EdgeInsets.all(24),child:Column(children:[Icon(m['state']=='pending'?Icons.hourglass_top:Icons.info_outline,size:64,color:_orange),const SizedBox(height:16),Text('Account ${_stateText(m['state'])}',style:const TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:_navy)),const SizedBox(height:10),Text(m['state']=='pending'?'Management must verify your business and contact information before you can book a driver.':_text(m['review_note']).isEmpty?'Contact management for account assistance.':_text(m['review_note']),textAlign:TextAlign.center),const SizedBox(height:20),FilledButton(style:_primary(),onPressed:_restore,child:const Text('Check approval status')),TextButton(onPressed:_logout,child:const Text('Sign out'))]))));
    return _MerchantHome(api:_authorizedCall,origin:widget.apiOrigin,merchant:m,onMerchant:(v)=>setState(()=>_merchant=v),onLogout:_logout);
  }
}

class _MerchantAuth extends StatefulWidget {
  final Future<void> Function(String,Map<String,dynamic>) onAuth;
  const _MerchantAuth({required this.onAuth});
  @override
  State<_MerchantAuth> createState()=>_MerchantAuthState();
}
class _MerchantAuthState extends State<_MerchantAuth>{
  final _form=GlobalKey<FormState>();
  final _email=TextEditingController(),_password=TextEditingController(),_name=TextEditingController(),_business=TextEditingController(),_phone=TextEditingController(),_address=TextEditingController(),_lat=TextEditingController(),_lng=TextEditingController();
  bool _register=false,_busy=false,_show=false,_consent=false;
  String _type='individual';String? _error;
  @override
  void dispose(){for(final c in [_email,_password,_name,_business,_phone,_address,_lat,_lng]){c.dispose();}super.dispose();}
  Future<void> _submit()async{
    if(_busy||!(_form.currentState?.validate()??false))return;
    setState((){_busy=true;_error=null;});
    try{
      final data=<String,dynamic>{'email':_email.text.trim(),'password':_password.text};
      if(_register){
        if(!_consent)throw const MarketFailure('Confirm consent before registering.');
        if(_password.text.length<12)throw const MarketFailure('Use at least 12 characters with letters and numbers.');
        final p=_checkedPin(_lat,_lng);
        data.addAll({'name':_name.text.trim(),'business_name':_business.text.trim(),'business_type':_type,'phone':_phone.text.trim(),'pickup_address':_address.text.trim(),'lat':p.latitude,'lng':p.longitude,'consent':true});
      }
      await widget.onAuth('/marketplace/auth/${_register?'register':'login'}',data);
    }catch(e){if(mounted)setState(()=>_error=_message(e));}
    finally{if(mounted)setState(()=>_busy=false);}
  }
  @override
  Widget build(BuildContext context)=>Scaffold(backgroundColor:_bg,appBar:AppBar(title:const Text('Merchant account')),body:SafeArea(child:Center(child:SingleChildScrollView(padding:const EdgeInsets.all(24),child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:500),child:Form(key:_form,child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Image.asset('assets/signin_logo.png',height:85),const SizedBox(height:18),Text(_register?'Set up your business':'Welcome, merchant!',style:const TextStyle(color:_navy,fontSize:28,fontWeight:FontWeight.w900)),const SizedBox(height:8),Text(_register?'Complete your account and pickup details. Management will review your registration.':'Sign in to discover nearby drivers and manage deliveries.'),const SizedBox(height:20),if(_error!=null)_ErrorCard(_error!),_field(_email,'Email address',type:TextInputType.emailAddress),_field(_password,'Password',obscure:!_show,suffix:IconButton(tooltip:_show?'Hide password':'Show password',onPressed:()=>setState(()=>_show=!_show),icon:Icon(_show?Icons.visibility_off:Icons.visibility))),if(_register)...[_field(_name,'Your name'),_field(_business,'Business or shop name'),DropdownButtonFormField<String>(initialValue:_type,decoration:const InputDecoration(labelText:'Business type'),items:const [DropdownMenuItem(value:'individual',child:Text('Individual seller')),DropdownMenuItem(value:'retail',child:Text('Retail shop')),DropdownMenuItem(value:'company',child:Text('Company')),DropdownMenuItem(value:'online',child:Text('Online store'))],onChanged:(v){if(v!=null)setState(()=>_type=v);}),const SizedBox(height:12),_field(_phone,'Mobile number',type:TextInputType.phone),_LocationFields(address:_address,lat:_lat,lng:_lng,label:'Pickup'),CheckboxListTile(contentPadding:EdgeInsets.zero,value:_consent,onChanged:(v)=>setState(()=>_consent=v??false),title:const Text('I consent to using my account, contact and pickup information to review my registration and arrange deliveries.'),controlAffinity:ListTileControlAffinity.leading)],const SizedBox(height:8),FilledButton(style:_primary(),onPressed:_busy?null:_submit,child:_busy?_spin():Text(_register?'Submit registration':'Sign in')),TextButton(onPressed:_busy?null:()=>setState((){_register=!_register;_error=null;}),child:Text(_register?'Already registered? Sign in':'Create merchant account')),const Text('Shopify store authorization is available after KRIYA360 account approval. KRIYA360 never requests your Shopify password.',textAlign:TextAlign.center,style:TextStyle(color:Colors.blueGrey,fontSize:12))])))))));
}

Future<void> _callPhone(BuildContext context,String phone)async{
  if(!RegExp(r'^\+?[0-9]{10,15}$').hasMatch(phone)){_notice(context,'Contact number unavailable.');return;}
  try{if(!await launchUrl(Uri(scheme:'tel',path:phone))&&context.mounted)_notice(context,'Unable to open your dialer.');}catch(e){if(context.mounted)_notice(context,'Unable to open your dialer.');}
}
Future<void> _navigate(BuildContext context,double lat,double lng)async{
  final url=Uri.https('www.google.com','/maps/dir/',{'api':'1','destination':'$lat,$lng'});
  try{if(!await launchUrl(url,mode:LaunchMode.externalApplication)&&context.mounted)_notice(context,'Unable to open navigation.');}catch(e){if(context.mounted)_notice(context,'Unable to open navigation.');}
}

class _MerchantHome extends StatefulWidget{
  final MarketCall api;final String origin;final Map<String,dynamic> merchant;
  final ValueChanged<Map<String,dynamic>> onMerchant;final Future<void> Function() onLogout;
  const _MerchantHome({required this.api,required this.origin,required this.merchant,required this.onMerchant,required this.onLogout});
  @override
  State<_MerchantHome> createState()=>_MerchantHomeState();
}
class _MerchantHomeState extends State<_MerchantHome>{
  int _tab=0;double _radius=5;bool _busy=false,_favoritesOnly=false;String? _error;String _vehicleFilter='';
  List<Map<String,dynamic>> _drivers=[],_bookings=[],_stores=[];
  Timer? _poll;
  @override
  void initState(){super.initState();_load();_poll=Timer.periodic(const Duration(seconds:20),(_){if(_tab==0||_tab==1)_load();});}
  @override
  void dispose(){_poll?.cancel();super.dispose();}
  Future<void> _load()async{
    if(_busy)return;final tab=_tab;
    setState(()=>_busy=true);
    try{
      if(tab==0){final v=_rows(await widget.api('/marketplace/drivers/nearby?radius_km=$_radius&favorites_only=$_favoritesOnly&vehicle=${Uri.encodeQueryComponent(_vehicleFilter)}','GET',null));if(mounted)setState(()=>_drivers=v);}
      else if(tab==1){final v=_rows(await widget.api('/marketplace/bookings','GET',null));if(mounted)setState(()=>_bookings=v);}
      else if(tab==2){final v=_rows(await widget.api('/integrations/shopify/stores','GET',null));if(mounted)setState(()=>_stores=v);}
      else{final m=_object(await widget.api('/marketplace/me','GET',null));if(mounted)widget.onMerchant(m);}
      if(mounted)setState(()=>_error=null);
    }catch(e){if(mounted)setState(()=>_error=_message(e));}
    finally{if(mounted){setState(()=>_busy=false);if(tab!=_tab){unawaited(_load());}}}
  }
  Future<void> _editPickup()async{
    final result=await Navigator.of(context).push<Map<String,dynamic>>(MaterialPageRoute(builder:(_)=>_PickupEdit(merchant:widget.merchant,api:widget.api)));
    if(!mounted||result==null)return;widget.onMerchant(result);setState(()=>_drivers=[]);await _load();
  }
  Future<void> _book({Map<String,dynamic>? driver,Map<String,dynamic>? order})async{
    final result=await Navigator.of(context).push<bool>(MaterialPageRoute(builder:(_)=>_BookingForm(api:widget.api,merchant:widget.merchant,driver:driver,order:order,radius:_radius)));
    if(mounted&&result==true){setState(()=>_tab=1);await _load();}
  }
  Future<void> _favorite(Map<String,dynamic> driver) async {
    try { await widget.api('/marketplace/drivers/${driver['id']}/favorite','PUT',{'saved':driver['favorite']!=true}); if(mounted)await _load(); } catch(e){if(mounted)_notice(context,_message(e));}
  }
  Future<void> _tracking(String id) async {
    if(!await _confirm(context,'Create a seven-day customer tracking link? Any previous link for this delivery will stop working.')||!mounted)return;
    try { final r=_object(await widget.api('/marketplace/bookings/$id/tracking-link','POST',null)); await Clipboard.setData(ClipboardData(text:_text(r['url']))); if(mounted)_notice(context,'Tracking link copied. Share it with your customer.'); } catch(e){if(mounted)_notice(context,_message(e));}
  }
  Future<void> _contact(Map<String,dynamic> driver)async{
    try{final contact=_object(await widget.api('/marketplace/drivers/${driver['id']}/contact','GET',null));if(!mounted)return;await showDialog<void>(context:context,builder:(ctx)=>AlertDialog(title:Text(_text(contact['name'])),content:SelectableText(_text(contact['phone'])),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Close')),FilledButton(onPressed:()=>_callPhone(ctx,_text(contact['phone'])),child:const Text('Call driver'))]));}catch(e){if(mounted)_notice(context,_message(e));}
  }
  Future<void> _action(String path,{Map<String,dynamic>? data})async{
    if(_busy)return;setState(()=>_busy=true);
    try{await widget.api(path,'POST',data);if(mounted)_notice(context,'Updated successfully.');}catch(e){if(mounted)_notice(context,_message(e));}
    finally{if(mounted){setState(()=>_busy=false);await _load();}}
  }
  Future<void> _connect()async{
    final shop=await _ask(context,'Connect Shopify store','Store domain (name.myshopify.com)');if(shop==null||!mounted)return;
    setState(()=>_busy=true);
    try{final r=_object(await widget.api('/integrations/shopify/connect','POST',{'shop':shop}));final url=Uri.parse(_text(r['authorization_url']));final origin=Uri.parse(widget.origin);
      if(url.scheme!='https'||url.host!=origin.host||url.port!=origin.port||url.path!='/api/integrations/shopify/authorize')throw const MarketFailure('Unexpected store authorization address.');
      if(!await launchUrl(url,mode:LaunchMode.externalApplication))throw const MarketFailure('Unable to open Shopify authorization.');
      if(mounted)_notice(context,'Complete authorization in your browser, then refresh Stores.');
    }catch(e){if(mounted)_notice(context,_message(e));}finally{if(mounted)setState(()=>_busy=false);}
  }
  Future<void> _orders(String shop)async{
    await Navigator.of(context).push(MaterialPageRoute(builder:(_)=>_ShopOrders(api:widget.api,shop:shop,onBook:(o) async {await _book(order:o);})));if(mounted)_load();
  }
  Widget _nearby(){
    final m=widget.merchant;final center=ll.LatLng((m['lat'] as num).toDouble(),(m['lng'] as num).toDouble());
    return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Card(child:ListTile(leading:const Icon(Icons.location_on,color:_orange),title:const Text('Pickup location'),subtitle:Text(_text(m['pickup_address'])),trailing:TextButton(onPressed:_busy?null:_editPickup,child:const Text('Change')))),const SizedBox(height:8),SizedBox(height:230,child:ClipRRect(borderRadius:BorderRadius.circular(15),child:_MarketMap(key:ValueKey('${center.latitude},${center.longitude}'),center:center,pins:[(center,'Your pickup'),for(final d in _drivers)(ll.LatLng((d['approx_lat'] as num).toDouble(),(d['approx_lng'] as num).toDouble()),_text(d['name']))]))),const SizedBox(height:10),const Text('Approximate driver positions before booking',style:TextStyle(fontSize:12,color:Colors.blueGrey)),Row(children:[Expanded(child:Text('${_drivers.length} available drivers',style:const TextStyle(fontSize:19,fontWeight:FontWeight.bold,color:_navy))),DropdownButton<double>(value:_radius,items:[1.0,3.0,5.0,10.0,20.0].map((r)=>DropdownMenuItem(value:r,child:Text('${r.toInt()} km'))).toList(),onChanged:_busy?null:(v){if(v!=null){setState(()=>_radius=v);_load();}})]),FilledButton.icon(style:_primary(),onPressed:_busy?null:()=>_book(),icon:const Icon(Icons.route),label:const Text('Find a driver for me')),SwitchListTile(contentPadding:EdgeInsets.zero,title:const Text('Favourite drivers only'),value:_favoritesOnly,onChanged:_busy?null:(v){setState(()=>_favoritesOnly=v);_load();}),Padding(padding:const EdgeInsets.only(bottom:8),child:DropdownButtonFormField<String>(initialValue:_vehicleFilter,decoration:const InputDecoration(labelText:'Vehicle filter'),items:const [DropdownMenuItem(value:'',child:Text('All vehicles')),DropdownMenuItem(value:'Bike',child:Text('Bike')),DropdownMenuItem(value:'Two Wheeler',child:Text('Two Wheeler')),DropdownMenuItem(value:'Car',child:Text('Car')),DropdownMenuItem(value:'Van',child:Text('Van')),DropdownMenuItem(value:'Truck',child:Text('Truck')),DropdownMenuItem(value:'Lorry',child:Text('Lorry'))],onChanged:_busy?null:(v){if(v!=null){setState(()=>_vehicleFilter=v);_load();}})),const SizedBox(height:10),if(_drivers.isEmpty&&!_busy)const Card(child:Padding(padding:EdgeInsets.all(18),child:Text('No available drivers in this area. Try a wider radius or refresh.'))),for(final d in _drivers)Card(child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(children:[const CircleAvatar(backgroundColor:_bg,child:Icon(Icons.local_shipping,color:_navy)),const SizedBox(width:12),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(_text(d['name']),style:const TextStyle(fontSize:17,fontWeight:FontWeight.bold)),Text('${_text(d['vehicle'])} • approx. ${d['distance_km']} km'),const Text('Licence verified · Available',style:TextStyle(color:Colors.green,fontSize:12)),Text(d['rating']==null?'Not rated yet · ${d['completed_deliveries']} completed':'★ ${d['rating']} (${d['rating_count']}) · ${d['completed_deliveries']} completed',style:const TextStyle(fontSize:12))])),IconButton(tooltip:d['favorite']==true?'Remove favourite':'Save favourite',onPressed:_busy?null:()=>_favorite(d),icon:Icon(d['favorite']==true?Icons.favorite:Icons.favorite_border,color:_orange))]),const SizedBox(height:12),Row(children:[Expanded(child:OutlinedButton.icon(onPressed:d['contact_available']==true&&!_busy?()=>_contact(d):null,icon:const Icon(Icons.call),label:const Text('Contact'))),const SizedBox(width:8),Expanded(child:FilledButton(style:_primary(),onPressed:_busy?null:()=>_book(driver:d),child:const Text('Request')))])]))) ]);
  }
  Widget _deliveryCard(Map<String,dynamic> b){
    final state=_text(b['state']),id=_text(b['id']);final active=['accepted','arrived','collected','in_transit'].contains(state);
    return Card(child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Row(children:[Expanded(child:Text(_text(b['title']),style:const TextStyle(fontSize:18,fontWeight:FontWeight.bold))),Chip(label:Text(_stateText(state)))]),Text('Driver: ${b['driver_name']}'),Text('Pickup: ${b['pickup_address']}'),Text('Destination: ${b['delivery_address']}'),if(b['problem']!=null&&_text(b['problem']).isNotEmpty)_ErrorCard(_text(b['problem'])),if(b['pickup_code']!=null)...[const SizedBox(height:12),Container(padding:const EdgeInsets.all(14),decoration:BoxDecoration(color:_orange.withValues(alpha:.08),borderRadius:BorderRadius.circular(12)),child:Column(children:[const Text('Pickup verification code'),SelectableText(_text(b['pickup_code']),style:const TextStyle(fontSize:28,fontWeight:FontWeight.w900,letterSpacing:5)),const Text('Share only when the correct driver collects your package.',textAlign:TextAlign.center,style:TextStyle(fontSize:12))]))],if(active&&b['driver_location'] is Map)...[const SizedBox(height:10),SizedBox(height:160,child:_MarketMap(center:ll.LatLng((b['driver_location']['lat'] as num).toDouble(),(b['driver_location']['lng'] as num).toDouble()),pins:[(ll.LatLng((b['driver_location']['lat'] as num).toDouble(),(b['driver_location']['lng'] as num).toDouble()),'Driver')]))],Wrap(spacing:6,children:[if(!['cancelled','rejected','expired'].contains(state))TextButton.icon(onPressed:_busy?null:()=>_tracking(id),icon:const Icon(Icons.link),label:const Text('Copy tracking link')),if(state=='completed'&&b['rating_given']!=true)TextButton.icon(onPressed:_busy?null:()async{final rating=await _askRating(context);if(rating!=null&&mounted)await _action('/marketplace/bookings/$id/rating',data:rating);},icon:const Icon(Icons.star_outline),label:const Text('Rate driver')),if(b['driver_phone']!=null)TextButton.icon(onPressed:()=>_callPhone(context,_text(b['driver_phone'])),icon:const Icon(Icons.call),label:const Text('Call')),if(['requested','accepted','arrived','collected','in_transit'].contains(state))TextButton.icon(onPressed:()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>_ChatPage(api:widget.api,path:'/marketplace/bookings/$id/messages'))),icon:const Icon(Icons.chat_bubble_outline),label:const Text('Chat')),if(['accepted','arrived'].contains(state))TextButton(onPressed:_busy?null:()=>_action('/marketplace/bookings/$id/renew-code'),child:const Text('Renew code')),if(['requested','accepted','arrived'].contains(state))TextButton(onPressed:_busy?null:()async{if(await _confirm(context,'Cancel this pickup?')&&mounted)await _action('/marketplace/bookings/$id/cancel');},child:const Text('Cancel pickup'))])])));
  }
  Widget _deliveries()=>Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[FilledButton.icon(style:_primary(),onPressed:_busy?null:()=>_book(),icon:const Icon(Icons.add),label:const Text('New delivery request')),if(_bookings.isEmpty&&!_busy)const Padding(padding:EdgeInsets.all(22),child:Text('No delivery requests yet.',textAlign:TextAlign.center)),for(final b in _bookings)_deliveryCard(b)]);
  Widget _marketPanel(List<Widget> children) => Container(
    margin: const EdgeInsets.only(bottom: 14), padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xffE1E7EF))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
  );
  Widget _accountStatus(String state) {
    final good = state == 'approved' || state == 'connected';
    final color = good ? const Color(0xff187647) : const Color(0xff8A5414);
    return Align(alignment: Alignment.centerLeft, child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: good ? const Color(0xffE2F5E9) : const Color(0xffFFF2DC), borderRadius: BorderRadius.circular(20)),
      child: Text(_stateText(state), style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12)),
    ));
  }
  Widget _profileField(IconData icon, String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: _navy, size: 22), const SizedBox(width: 13),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(color: Color(0xff62748A), fontSize: 12)), const SizedBox(height: 4),
        SelectableText(value.isEmpty ? 'Not provided' : value, style: const TextStyle(color: _navy, fontSize: 15, fontWeight: FontWeight.w600)),
      ])),
    ]),
  );
  Widget _storePage() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    const Text('Connected stores', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: _navy)),
    const SizedBox(height: 6), const Text('Manage your e-commerce integrations.', style: TextStyle(color: Color(0xff62748A))), const SizedBox(height: 18),
    _marketPanel([
      Row(children: [Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xffE9F4E4), borderRadius: BorderRadius.circular(14)), child: const Icon(Icons.shopping_bag_outlined, color: Color(0xff397B31), size: 30)), const SizedBox(width: 14),
        const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Shopify', style: TextStyle(color: _navy, fontSize: 20, fontWeight: FontWeight.w800)), Text('Store integration', style: TextStyle(color: Color(0xff62748A)))]))]),
      const SizedBox(height: 16), if (_error == null && (!_busy || _stores.isNotEmpty)) _accountStatus(_stores.any((st) => st['state'] == 'connected') ? 'connected' : 'not connected'),
      const SizedBox(height: 14), const Text('Import authorized store orders and arrange package collection and delivery. Confirm delivery details manually.', style: TextStyle(height: 1.5, color: _navy)),
      const SizedBox(height: 18), FilledButton.icon(style: _primary(), onPressed: _busy ? null : _connect, icon: const Icon(Icons.link), label: const Text('Connect Shopify store')),
      const SizedBox(height: 8), const Text('Complete secure authorization in your browser, then refresh this screen.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: Color(0xff62748A))),
    ]),
    if (_stores.isNotEmpty) const Padding(padding: EdgeInsets.only(bottom: 10), child: Text('Your stores', style: TextStyle(color: _navy, fontSize: 18, fontWeight: FontWeight.w700))),
    for (final st in _stores) _marketPanel([
      Row(children: [const Icon(Icons.storefront_outlined, color: _orange), const SizedBox(width: 10), Expanded(child: Text(_text(st['shop']), style: const TextStyle(color: _navy, fontWeight: FontWeight.w700, fontSize: 16)))]),
      const SizedBox(height: 12), _accountStatus(_text(st['state'])),
      if (st['state'] == 'connected') ...[
        const Divider(height: 28),
        OutlinedButton.icon(onPressed: _busy ? null : () => _action('/integrations/shopify/stores/${st['shop']}/sync'), icon: const Icon(Icons.sync), label: const Text('Sync orders')),
        OutlinedButton.icon(onPressed: _busy ? null : () => _orders(_text(st['shop'])), icon: const Icon(Icons.receipt_long_outlined), label: const Text('View orders')),
        TextButton.icon(onPressed: _busy ? null : () async {if (await _confirm(context, 'Disconnect this store? Uninstall the app in Shopify as well to revoke access.') && mounted) await _action('/integrations/shopify/stores/${st['shop']}/disconnect');}, icon: const Icon(Icons.link_off, color: Color(0xffB42318)), label: const Text('Disconnect', style: TextStyle(color: Color(0xffB42318)))),
      ],
    ]),
    const Padding(padding: EdgeInsets.symmetric(horizontal: 4), child: Text('Shopify fulfillment writeback is currently unavailable.', style: TextStyle(fontSize: 12, color: Color(0xff62748A)))),
  ]);
  Widget _profile() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    const Text('My profile', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: _navy)), const SizedBox(height: 6),
    const Text('Manage your merchant account.', style: TextStyle(color: Color(0xff62748A))), const SizedBox(height: 18),
    Container(padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: _navy, borderRadius: BorderRadius.circular(20)), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: _orange, borderRadius: BorderRadius.circular(16)), child: const Icon(Icons.storefront, color: Colors.white, size: 32)), const SizedBox(width: 15),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(_text(widget.merchant['business_name']), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: Colors.white)), const SizedBox(height: 4), const Text('Merchant account', style: TextStyle(color: Color(0xffD2DCEB))), const SizedBox(height: 10), _accountStatus(_text(widget.merchant['state']))])),
    ])), const SizedBox(height: 18),
    _marketPanel([
      const Text('Account information', style: TextStyle(color: _navy, fontSize: 17, fontWeight: FontWeight.w700)),
      _profileField(Icons.person_outline, 'Contact name', _text(widget.merchant['name'])), const Divider(height: 1),
      _profileField(Icons.phone_outlined, 'Phone number', _text(widget.merchant['phone'])), const Divider(height: 1),
      _profileField(Icons.mail_outline, 'Email address', _text(widget.merchant['email'])),
    ]),
    _marketPanel([
      const Text('Pickup location', style: TextStyle(color: _navy, fontSize: 17, fontWeight: FontWeight.w700)),
      _profileField(Icons.location_on_outlined, 'Registered pickup address', _text(widget.merchant['pickup_address'])),
      OutlinedButton.icon(onPressed: _busy ? null : _editPickup, icon: const Icon(Icons.edit_location_alt_outlined), label: const Text('Change pickup location')),
    ]),
    _marketPanel([TextButton.icon(onPressed: _busy ? null : () async {if (await _confirm(context, 'Sign out of your merchant account?') && mounted) await widget.onLogout();}, icon: const Icon(Icons.logout, color: Color(0xffB42318)), label: const Text('Sign out', style: TextStyle(color: Color(0xffB42318), fontWeight: FontWeight.w700)))]),
    Center(child: Image.asset('assets/company_logo.png', width: 120, height: 42, fit: BoxFit.contain, semanticLabel: 'IntProSec company logo')),
  ]);
  @override
  Widget build(BuildContext context)=>Scaffold(backgroundColor:_bg,appBar:AppBar(title:const Text('KRIYA360 Merchant'),actions:[IconButton(tooltip:'Refresh',onPressed:_busy?null:_load,icon:const Icon(Icons.refresh))]),body:SafeArea(child:RefreshIndicator(onRefresh:_load,child:ListView(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(14),children:[if(_busy)const LinearProgressIndicator(),if(_error!=null)_ErrorCard(_error!,retry:_load),switch(_tab){0=>_nearby(),1=>_deliveries(),2=>_storePage(),_=>_profile()}]))),bottomNavigationBar:NavigationBar(selectedIndex:_tab,onDestinationSelected:(v){setState((){_tab=v;_error=null;});_load();},destinations:const [NavigationDestination(icon:Icon(Icons.local_shipping_outlined),label:'Drivers'),NavigationDestination(icon:Icon(Icons.inventory_2_outlined),label:'Deliveries'),NavigationDestination(icon:Icon(Icons.storefront_outlined),label:'Stores'),NavigationDestination(icon:Icon(Icons.person_outline),label:'Profile')]));
}

class _PickupEdit extends StatefulWidget{
  final Map<String,dynamic> merchant;final MarketCall api;
  const _PickupEdit({required this.merchant,required this.api});
  @override State<_PickupEdit> createState()=>_PickupEditState();
}
class _PickupEditState extends State<_PickupEdit>{
  late final _address=TextEditingController(text:_text(widget.merchant['pickup_address'])),_lat=TextEditingController(text:_text(widget.merchant['lat'])),_lng=TextEditingController(text:_text(widget.merchant['lng']));
  final _form=GlobalKey<FormState>();bool _busy=false;String? _error;
  @override void dispose(){_address.dispose();_lat.dispose();_lng.dispose();super.dispose();}
  Future<void> _save()async{if(_busy||!(_form.currentState?.validate()??false))return;setState(()=>_busy=true);try{final p=_checkedPin(_lat,_lng);final r=_object(await widget.api('/marketplace/me/pickup','PUT',{'address':_address.text.trim(),'lat':p.latitude,'lng':p.longitude}));if(mounted)Navigator.pop(context,r);}catch(e){if(mounted)setState(()=>_error=_message(e));}finally{if(mounted)setState(()=>_busy=false);}}
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Pickup location')),body:SingleChildScrollView(padding:const EdgeInsets.all(20),child:Form(key:_form,child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[if(_error!=null)_ErrorCard(_error!),_LocationFields(address:_address,lat:_lat,lng:_lng,label:'Pickup'),FilledButton(style:_primary(),onPressed:_busy?null:_save,child:_busy?_spin():const Text('Save pickup location'))]))));
}

class _BookingForm extends StatefulWidget{
  final MarketCall api;final Map<String,dynamic> merchant;final Map<String,dynamic>? driver,order;final double radius;
  const _BookingForm({required this.api,required this.merchant,this.driver,this.order,required this.radius});
  @override State<_BookingForm> createState()=>_BookingFormState();
}
class _BookingFormState extends State<_BookingForm>{
  final _form=GlobalKey<FormState>();final _requestKey=_key();
  late final _title=TextEditingController(text:_text(widget.order?['name']));
  final _address=TextEditingController(),_lat=TextEditingController(),_lng=TextEditingController(),_customer=TextEditingController(),_phone=TextEditingController(),_hours=TextEditingController(text:'2'),_weight=TextEditingController(text:'0'),_instructions=TextEditingController();
  bool _busy=false;String? _error;
  @override void dispose(){for(final c in [_title,_address,_lat,_lng,_customer,_phone,_hours,_weight,_instructions]){c.dispose();}super.dispose();}
  Future<void> _submit()async{
    if(_busy||!(_form.currentState?.validate()??false))return;
    setState((){_busy=true;_error=null;});
    try{final p=_checkedPin(_lat,_lng);final hours=double.tryParse(_hours.text),weight=double.tryParse(_weight.text);if(hours==null||!hours.isFinite||hours<=0||hours>168||weight==null||!weight.isFinite||weight<0)throw const MarketFailure('Enter a valid delivery deadline and package weight.');
      await widget.api('/marketplace/bookings','POST',{'request_key':_requestKey,'driver_id':widget.driver?['id'],'title':_title.text.trim(),'delivery_address':_address.text.trim(),'delivery_lat':p.latitude,'delivery_lng':p.longitude,'customer_name':_customer.text.trim(),'customer_phone':_phone.text.trim(),'due_at':DateTime.now().toUtc().add(Duration(minutes:(hours*60).round())).toIso8601String(),'weight_kg':weight,'instructions':_instructions.text.trim(),'radius_km':widget.radius,if(widget.order!=null)'shopify_order_id':widget.order!['id'],if(widget.order!=null)'shopify_shop':widget.order!['shop']});
      if(mounted)Navigator.pop(context,true);
    }catch(e){if(mounted)setState(()=>_error=_message(e));}finally{if(mounted)setState(()=>_busy=false);}
  }
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Request pickup')),body:SafeArea(child:SingleChildScrollView(padding:const EdgeInsets.all(20),child:Form(key:_form,child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Card(child:Padding(padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('Pickup: ${widget.merchant['pickup_address']}'),Text(widget.driver==null?'Find an eligible nearby driver':'Driver: ${widget.driver!['name']}'),if(widget.order!=null)Text('Shopify order: ${widget.order!['name']}'),const SizedBox(height:6),const Text('Requests are subject to driver acceptance. This pilot does not charge or collect payments.')] ))),if(_error!=null)_ErrorCard(_error!),_field(_title,'Package or order name'),_LocationFields(address:_address,lat:_lat,lng:_lng,label:'Delivery'),_field(_customer,'Recipient name'),_field(_phone,'Recipient phone',type:TextInputType.phone),_field(_hours,'Delivery deadline (hours from now)',type:const TextInputType.numberWithOptions(decimal:true)),_field(_weight,'Package weight (kg)',type:const TextInputType.numberWithOptions(decimal:true)),_field(_instructions,'Special instructions',required:false,maxLines:3),FilledButton(style:_primary(),onPressed:_busy?null:_submit,child:_busy?_spin():const Text('Send pickup request')),const Text('A request expires after five minutes if it is not accepted.',textAlign:TextAlign.center,style:TextStyle(color:Colors.blueGrey,fontSize:12))])))));
}

class _ShopOrders extends StatefulWidget{
  final MarketCall api;final String shop;final Future<void> Function(Map<String,dynamic>) onBook;
  const _ShopOrders({required this.api,required this.shop,required this.onBook});
  @override State<_ShopOrders> createState()=>_ShopOrdersState();
}
class _ShopOrdersState extends State<_ShopOrders>{
  bool _busy=false;String? _error;List<Map<String,dynamic>> _orders=[];
  @override void initState(){super.initState();_load();}
  Future<void> _load()async{if(_busy)return;setState(()=>_busy=true);try{final rows=_rows(await widget.api('/integrations/shopify/stores/${widget.shop}/orders','GET',null));if(mounted)setState((){_orders=rows;_error=null;});}catch(e){if(mounted)setState(()=>_error=_message(e));}finally{if(mounted)setState(()=>_busy=false);}}
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Shopify orders'),actions:[IconButton(tooltip:'Refresh',onPressed:_busy?null:_load,icon:const Icon(Icons.refresh))]),body:ListView(padding:const EdgeInsets.all(16),children:[if(_busy)const LinearProgressIndicator(),if(_error!=null)_ErrorCard(_error!,retry:_load),if(_orders.isEmpty&&!_busy)const Text('No synchronized orders. Return to Stores and choose Sync orders.'),for(final o in _orders)Card(child:ListTile(title:Text(_text(o['name'])),subtitle:Text(o['cancelled']==true?'Cancelled':_stateText(o['fulfillment_status'])),trailing:TextButton(onPressed:o['booking_eligible']==true?()async{await widget.onBook(o);if(context.mounted)Navigator.pop(context);}:null,child:const Text('Book pickup'))))]));
}

Future<String?> _ask(BuildContext context,String title,String label,{TextInputType? type})async{
  final c=TextEditingController();
  try{return await showDialog<String>(context:context,builder:(ctx)=>AlertDialog(title:Text(title),content:TextField(controller:c,keyboardType:type,autofocus:true,decoration:InputDecoration(labelText:label)),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Cancel')),FilledButton(onPressed:(){if(c.text.trim().isNotEmpty)Navigator.pop(ctx,c.text.trim());},child:const Text('Continue'))]));}finally{c.dispose();}
}
Future<bool> _confirm(BuildContext context,String message)async=>await showDialog<bool>(context:context,builder:(ctx)=>AlertDialog(title:const Text('Confirm action'),content:Text(message),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:const Text('Go back')),FilledButton(onPressed:()=>Navigator.pop(ctx,true),child:const Text('Confirm'))]))??false;

class _ChatPage extends StatefulWidget{
  final MarketCall api;final String path;
  const _ChatPage({required this.api,required this.path});
  @override State<_ChatPage> createState()=>_ChatPageState();
}
class _ChatPageState extends State<_ChatPage>{
  final _textController=TextEditingController();List<Map<String,dynamic>> _messages=[];bool _busy=false,_sending=false;String? _error;Timer? _poll;
  @override void initState(){super.initState();_load();_poll=Timer.periodic(const Duration(seconds:8),(_)=>_load());}
  @override void dispose(){_poll?.cancel();_textController.dispose();super.dispose();}
  Future<void> _load()async{if(_busy)return;_busy=true;try{final rows=_rows(await widget.api(widget.path,'GET',null));if(mounted)setState((){_messages=rows;_error=null;});}catch(e){if(mounted)setState(()=>_error=_message(e));}finally{_busy=false;}}
  Future<void> _send()async{if(_sending||_textController.text.trim().isEmpty)return;setState(()=>_sending=true);try{await widget.api(widget.path,'POST',{'body':_textController.text.trim()});if(mounted){_textController.clear();await _load();}}catch(e){if(mounted)setState(()=>_error=_message(e));}finally{if(mounted)setState(()=>_sending=false);}}
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Pickup conversation')),body:SafeArea(child:Column(children:[if(_error!=null)_ErrorCard(_error!,retry:_load),Expanded(child:ListView(padding:const EdgeInsets.all(16),children:[const Text('Messages are visible only to the booking participants.',style:TextStyle(color:Colors.blueGrey,fontSize:12)),for(final m in _messages)Card(child:ListTile(title:Text(_text(m['body'])),subtitle:Text('${_stateText(m['sender_role'])} • ${_text(m['created_at'])}')))])),Padding(padding:const EdgeInsets.all(12),child:Row(children:[Expanded(child:TextField(controller:_textController,maxLength:1000,maxLines:2,decoration:const InputDecoration(hintText:'Write a message',counterText:''))),IconButton(tooltip:'Send',onPressed:_sending?null:_send,icon:_sending?const CircularProgressIndicator():const Icon(Icons.send))]))])));
}

/// Accessible from existing DriverHome; existing delivery and attendance UI stays intact.
class DriverMarketplace extends StatefulWidget{
  final MarketCall api;
  const DriverMarketplace({super.key,required this.api});
  @override State<DriverMarketplace> createState()=>_DriverMarketplaceState();
}
class _DriverMarketplaceState extends State<DriverMarketplace>{
  List<Map<String,dynamic>> _bookings=[];Map<String,dynamic> _visibility={};bool _busy=false;String? _error;Timer? _poll;
  @override void initState(){super.initState();_load();_poll=Timer.periodic(const Duration(seconds:15),(_)=>_load());}
  @override void dispose(){_poll?.cancel();super.dispose();}
  Future<void> _load()async{if(_busy)return;setState(()=>_busy=true);try{final values=await Future.wait([widget.api('/marketplace/driver/visibility','GET',null),widget.api('/marketplace/driver/bookings','GET',null)]);if(mounted)setState((){_visibility=_object(values[0]);_bookings=_rows(values[1]);_error=null;});}catch(e){if(mounted)setState(()=>_error=_message(e));}finally{if(mounted)setState(()=>_busy=false);}}
  Future<void> _visibilityChange(bool enabled,bool share)async{
    if(enabled&&_visibility['enabled']!=true){if(!await _confirm(context,'Allow verified merchants to discover your approximate location, name and vehicle when you are on shift, idle and GPS is fresh?'))return;}
    if(share&&_visibility['share_phone']!=true){if(!mounted||!await _confirm(context,'Allow verified nearby merchants to view your phone number and call you?'))return;}
    if(!mounted)return;setState(()=>_busy=true);try{final v=_object(await widget.api('/marketplace/driver/visibility','PUT',{'enabled':enabled,'share_phone':share}));if(mounted)setState(()=>_visibility=v);}catch(e){if(mounted)_notice(context,_message(e));}finally{if(mounted){setState(()=>_busy=false);await _load();}}
  }
  Future<void> _act(String id,String action,{Map<String,dynamic>? data})async{
    if(_busy)return;setState(()=>_busy=true);try{await widget.api('/marketplace/driver/bookings/$id/$action','POST',data);if(mounted)_notice(context,action=='collect'?'Pickup verified. Open My Tasks to start the delivery.':'Pickup updated.');}catch(e){if(mounted)_notice(context,_message(e));}finally{if(mounted){setState(()=>_busy=false);await _load();}}
  }
  Future<void> _arrival(String id,{String? code})async{
    if(_busy)return;setState(()=>_busy=true);
    try{final p=await _gps();if(!mounted)return;setState(()=>_busy=false);await _act(id,code==null?'arrive':'collect',data:{'lat':p.latitude,'lng':p.longitude,'accuracy_m':p.accuracy,if(code!=null)'code':code});}catch(e){if(mounted){_notice(context,_message(e));setState(()=>_busy=false);}}
  }
  Widget _booking(Map<String,dynamic> b){final state=_text(b['state']),id=_text(b['id']);return Card(child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Row(children:[Expanded(child:Text(_text(b['title']),style:const TextStyle(fontWeight:FontWeight.bold,fontSize:18))),Chip(label:Text(_stateText(state)))]),Text('Merchant: ${b['merchant_name']}'),Text('Pickup: ${b['pickup_address']}'),Text('Destination: ${b['delivery_address']}'),Text('Weight: ${b['weight_kg']} kg'),if(_text(b['instructions']).isNotEmpty)Text(_text(b['instructions'])),if(state=='requested')Row(children:[Expanded(child:OutlinedButton(onPressed:_busy?null:()=>_act(id,'reject'),child:const Text('Decline'))),const SizedBox(width:8),Expanded(child:FilledButton(style:_primary(),onPressed:_busy?null:()=>_act(id,'accept'),child:const Text('Accept pickup')))]),if(['accepted','arrived'].contains(state))... [Wrap(spacing:6,children:[TextButton.icon(onPressed:()=>_navigate(context,(b['pickup_lat'] as num).toDouble(),(b['pickup_lng'] as num).toDouble()),icon:const Icon(Icons.directions),label:const Text('Navigate')),if(b['merchant_phone']!=null)TextButton.icon(onPressed:()=>_callPhone(context,_text(b['merchant_phone'])),icon:const Icon(Icons.call),label:const Text('Call merchant'))]),if(state=='accepted')FilledButton(style:_primary(),onPressed:_busy?null:()=>_arrival(id),child:const Text('Confirm arrival')),if(state=='arrived')FilledButton(style:_primary(),onPressed:_busy?null:()async{final code=await _ask(context,'Verify pickup','Merchant’s six-digit pickup code',type:TextInputType.number);if(code!=null&&mounted){if(!RegExp(r'^\d{6}$').hasMatch(code)){_notice(context,'Enter the six-digit pickup code.');return;}await _arrival(id,code:code);}},child:const Text('Verify and collect'))],if(['collected','in_transit'].contains(state))const Text('Package collected. Manage the delivery using My Tasks.'),if(state=='completed'&&b['rating_given']!=true)TextButton.icon(onPressed:_busy?null:()async{final rating=await _askRating(context);if(rating!=null&&mounted)await _act(id,'rating',data:rating);},icon:const Icon(Icons.star_outline),label:const Text('Rate merchant')),if(['requested','accepted','arrived','collected','in_transit'].contains(state))Wrap(spacing:6,children:[TextButton.icon(onPressed:()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>_ChatPage(api:widget.api,path:'/marketplace/driver/bookings/$id/messages'))),icon:const Icon(Icons.chat_bubble_outline),label:const Text('Chat')),if(state!='requested')TextButton(onPressed:_busy?null:()async{final reason=await _ask(context,'Report pickup issue','Describe the problem');if(reason!=null&&mounted)await _act(id,'problem',data:{'reason':reason});},child:const Text('Report issue'))])])));}
  @override Widget build(BuildContext context)=>Scaffold(backgroundColor:_bg,appBar:AppBar(title:const Text('Merchant pickups'),actions:[IconButton(tooltip:'Refresh',onPressed:_busy?null:_load,icon:const Icon(Icons.refresh))]),body:RefreshIndicator(onRefresh:_load,child:ListView(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(14),children:[if(_busy)const LinearProgressIndicator(),if(_error!=null)_ErrorCard(_error!,retry:_load),Card(child:Column(children:[SwitchListTile(title:const Text('Available to merchants'),subtitle:const Text('Appear only when on shift, idle and GPS is fresh.'),value:_visibility['enabled']==true,onChanged:_busy?null:(v)=>_visibilityChange(v,v&&_visibility['share_phone']==true)),SwitchListTile(title:const Text('Share my phone with verified merchants'),value:_visibility['share_phone']==true,onChanged:_busy||_visibility['enabled']!=true?null:(v)=>_visibilityChange(true,v)),ListTile(leading:Icon(_visibility['eligible_now']==true?Icons.check_circle:Icons.info_outline,color:_visibility['eligible_now']==true?Colors.green:Colors.blueGrey),title:Text(_visibility['eligible_now']==true?'Visible to nearby merchants':'Not currently discoverable'))])),const SizedBox(height:12),const Text('Pickup requests',style:TextStyle(fontSize:20,fontWeight:FontWeight.w900,color:_navy)),if(_bookings.isEmpty&&!_busy)const Padding(padding:EdgeInsets.all(20),child:Text('No merchant pickup requests yet.')),for(final b in _bookings)_booking(b)])));
}

Future<Map<String,dynamic>?> _askRating(BuildContext context) async {
  int stars=5;
  return showDialog<Map<String,dynamic>>(context:context,builder:(ctx)=>StatefulBuilder(builder:(context,setDialog)=>AlertDialog(title:const Text('Rate completed delivery'),content:Row(mainAxisAlignment:MainAxisAlignment.center,children:List.generate(5,(i)=>IconButton(tooltip:'${i+1} stars',onPressed:()=>setDialog(()=>stars=i+1),icon:Icon(i<stars?Icons.star:Icons.star_outline,color:_orange)))),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(ctx,<String,dynamic>{'stars':stars}),child:const Text('Submit'))])));
}
