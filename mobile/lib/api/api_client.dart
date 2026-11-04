import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
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
    bool? requireHttps,
  }) : _http = httpClient ?? http.Client() {
    // Dernier garde-fou : même si la configuration est contournée, une version release
    // n'enverra jamais le jeton ni les données des voyageurs en clair.
    if ((requireHttps ?? kReleaseMode) && !baseUrl.toLowerCase().startsWith('https://')) {
      throw StateError('ApiClient : HTTPS obligatoire (reçu « $baseUrl »).');
    }
  }

  final String baseUrl;
  final TokenStorage tokens;
  final Duration timeout;
  final http.Client _http;

  /// Appelé quand la session ne peut plus être renouvelée (refresh refusé).
  void Function()? onSessionExpired;

  Future<Object?>? _refreshing;

  Future<Object?> get(String path) => _request('GET', path);

  Future<Object?> delete(String path) => _request('DELETE', path);

  Future<Object?> patch(String path, {Object? body}) => _request('PATCH', path, body: body);

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
        'PATCH' => _http.patch(
            uri,
            headers: allHeaders,
            body: body == null ? null : jsonEncode(body),
          ),
        'DELETE' => _http.delete(uri, headers: allHeaders),
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
  /// (session expirée) ; laisse remonter [NetworkException] si le réseau manque, et
  /// [ApiException] si le serveur est en panne, pour ne pas déconnecter un utilisateur
  /// simplement hors ligne ou mal servi.
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
    final status = response.statusCode;
    if (status == 408 || status == 429 || status >= 500) {
      // Une panne du serveur ne dit rien de la session : on la garde (un chauffeur en route n'est pas déconnecté),
      // l'appel échoue comme une erreur passagère et sera repris.
      throw ApiException(status, extractErrorMessage(_decodeBody(response)) ?? 'Erreur $status', _decodeBody(response));
    }
    if (status < 200 || status >= 300) return null;

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
