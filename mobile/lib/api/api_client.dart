import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../auth/token_storage.dart';
import 'api_exception.dart';

/// Client HTTP de l'API Django : ajoute le jeton JWT et le rafraîchit sur 401,
/// comme le fait le frontend web (`frontend/src/api/client.js`).
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.tokens,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 15),
  }) : _http = httpClient ?? http.Client();

  final String baseUrl;
  final TokenStorage tokens;
  final Duration timeout;
  final http.Client _http;

  /// Appelé quand la session ne peut plus être renouvelée (refresh refusé).
  void Function()? onSessionExpired;

  Future<Object?>? _refreshing;

  Future<Object?> get(String path) => _request('GET', path);

  Future<Object?> post(
    String path, {
    Object? body,
    Map<String, String>? headers,
    bool auth = true,
  }) =>
      _request('POST', path, body: body, headers: headers, auth: auth);

  Future<Object?> _request(
    String method,
    String path, {
    Object? body,
    Map<String, String>? headers,
    bool auth = true,
  }) async {
    var response = await _send(
      method,
      path,
      body,
      headers,
      auth ? await tokens.readAccess() : null,
    );

    if (response.statusCode == 401 && auth) {
      final newAccess = await _refreshAccessToken();
      if (newAccess != null) {
        response = await _send(method, path, body, headers, newAccess);
      } else {
        await tokens.clear();
        onSessionExpired?.call();
      }
    }
    return _decode(response);
  }

  Future<http.Response> _send(
    String method,
    String path,
    Object? body,
    Map<String, String>? headers,
    String? access,
  ) async {
    final uri = Uri.parse('$baseUrl$path');
    final allHeaders = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...?headers,
      if (access != null) 'Authorization': 'Bearer $access',
    };
    try {
      final Future<http.Response> call = switch (method) {
        'GET' => _http.get(uri, headers: allHeaders),
        'POST' => _http.post(
            uri,
            headers: allHeaders,
            body: body == null ? null : jsonEncode(body),
          ),
        _ => throw ArgumentError('Méthode HTTP non prise en charge : $method'),
      };
      return await call.timeout(timeout);
    } on TimeoutException {
      throw const NetworkException('Le serveur ne répond pas (délai dépassé).');
    } on http.ClientException catch (e) {
      throw NetworkException('Serveur injoignable : ${e.message}');
    }
  }

  /// Renouvelle le jeton d'accès. Retourne null si le refresh est absent ou refusé
  /// (session expirée) ; laisse remonter [NetworkException] si le réseau manque,
  /// pour ne pas déconnecter un utilisateur simplement hors ligne.
  Future<String?> _refreshAccessToken() async {
    final pending = _refreshing;
    if (pending != null) return await pending as String?;

    final future = _doRefresh();
    _refreshing = future;
    try {
      return await future;
    } finally {
      _refreshing = null;
    }
  }

  Future<String?> _doRefresh() async {
    final refresh = await tokens.readRefresh();
    if (refresh == null) return null;

    final response = await _send('POST', '/auth/refresh/', {'refresh': refresh}, null, null);
    if (response.statusCode < 200 || response.statusCode >= 300) return null;

    final data = _decodeBody(response);
    final access = data is Map ? data['access'] as String? : null;
    if (access == null) return null;
    await tokens.save(access: access);
    return access;
  }

  Object? _decodeBody(http.Response response) {
    if (response.body.isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      return null;
    }
  }

  Object? _decode(http.Response response) {
    final data = _decodeBody(response);
    if (response.statusCode >= 200 && response.statusCode < 300) return data;
    throw ApiException(
      response.statusCode,
      extractErrorMessage(data) ?? 'Erreur ${response.statusCode}',
      data,
    );
  }
}
