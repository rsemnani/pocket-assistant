# Keep Vosk + JNA native bindings.
-keep class org.vosk.** { *; }
-keep class com.sun.jna.** { *; }
-dontwarn java.awt.**

# kotlinx.serialization generated serializers.
-keepclassmembers class **$$serializer { *; }
-keepclasseswithmembers class * {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.pocketassistant.app.net.** { *; }

# Retrofit / OkHttp.
-dontwarn okhttp3.**
-dontwarn retrofit2.**
-keepattributes Signature, RuntimeVisibleAnnotations, AnnotationDefault
