/// L'utilisateur connecté (réponse de `/auth/me/`).
class AppUser {
  const AppUser({
    required this.id,
    required this.username,
    required this.role,
    this.firstName = '',
    this.lastName = '',
    this.companyName,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    final company = json['company'];
    return AppUser(
      id: json['id'] as int,
      username: json['username'] as String,
      role: json['role'] as String,
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
      companyName: company is Map ? company['name'] as String? : null,
    );
  }

  final int id;
  final String username;
  final String role;
  final String firstName;
  final String lastName;
  final String? companyName;

  String get displayName {
    final full = '$firstName $lastName'.trim();
    return full.isEmpty ? username : full;
  }

  /// Même forme que `/auth/me/`, pour pouvoir le mettre en cache tel quel.
  Map<String, dynamic> toJson() => {
        'id': id,
        'username': username,
        'role': role,
        'first_name': firstName,
        'last_name': lastName,
        'company': companyName == null ? null : {'name': companyName},
      };
}
