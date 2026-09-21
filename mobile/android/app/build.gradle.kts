import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Signature de la version release.
//
// La clé vient de android/key.properties (ignoré par git, avec le keystore : voir mobile/TEST_TELEPHONES.md) :
//   storeFile=<chemin absolu du .jks>   storePassword=…   keyAlias=…   keyPassword=…
// Android n'accepte de mettre à jour une application que si la nouvelle version est signée par la MÊME clé :
// la perdre, c'est ne plus pouvoir mettre à jour les téléphones déjà installés.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val signatureConfiguree = keystorePropertiesFile.exists()
if (signatureConfiguree) {
    keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

// Sans clé, on refuse de fabriquer un APK release plutôt que de le signer en silence avec la clé de débogage
// (publique : n'importe qui pourrait publier une « mise à jour » de l'application). Pour un essai purement local,
// ALLOW_DEBUG_SIGNING=1 rétablit l'ancien comportement.
val signatureDebugAutorisee = System.getenv("ALLOW_DEBUG_SIGNING") == "1"

android {
    namespace = "ci.transportcoord.transport_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    signingConfigs {
        if (signatureConfiguree) {
            create("release") {
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "ci.transportcoord.transport_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            signingConfig = when {
                signatureConfiguree -> signingConfigs.getByName("release")
                signatureDebugAutorisee -> signingConfigs.getByName("debug")
                else -> null
            }
        }
    }
}

gradle.taskGraph.whenReady {
    val fabriqueUneRelease = allTasks.any { tache ->
        val nom = tache.name
        nom.contains("Release") && (nom.startsWith("assemble") || nom.startsWith("bundle") || nom.startsWith("package"))
    }
    if (fabriqueUneRelease && !signatureConfiguree && !signatureDebugAutorisee) {
        throw GradleException(
            "Aucune cle de signature : creez android/key.properties (voir mobile/TEST_TELEPHONES.md), " +
                "ou definissez ALLOW_DEBUG_SIGNING=1 pour un essai local (APK non distribuable)."
        )
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
