from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'hook'
OUT.mkdir(exist_ok=True)

def run(*args):
    subprocess.run([str(a) for a in args], check=True)

(OUT / 'AndroidManifest.xml').write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.henry.pixellauncher.compat" android:versionCode="3" android:versionName="0.3.0"><uses-sdk android:minSdkVersion="36" android:targetSdkVersion="36"/><application android:hasCode="true" android:label="Pixel Launcher Compatibility Hook" android:allowBackup="false"><meta-data android:name="xposedmodule" android:value="true"/><meta-data android:name="xposeddescription" android:value="Pixel Launcher scoped optional automation fallback"/><meta-data android:name="xposedminversion" android:value="82"/></application></manifest>''', encoding='utf-8')
run(ROOT / 'tools/aapt2.exe', 'link', '-I', ROOT / 'framework-res.apk', '--manifest', OUT / 'AndroidManifest.xml', '-o', OUT / 'template.apk')
run('java', '-jar', ROOT / 'tools/apktool.jar', 'd', '-f', '-r', OUT / 'template.apk', '-o', OUT / 'decoded')
SRC = OUT / 'decoded/smali/dev/henry/pixellauncher/compat'
SRC.mkdir(parents=True, exist_ok=True)
(SRC / 'Entry.smali').write_text('''.class public Ldev/henry/pixellauncher/compat/Entry;
.super Ljava/lang/Object;
.implements Lde/robv/android/xposed/IXposedHookLoadPackage;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public handleLoadPackage(Lde/robv/android/xposed/callbacks/XC_LoadPackage$LoadPackageParam;)V
    .locals 4
    const-string v0, "com.google.android.apps.nexuslauncher"
    iget-object v1, p1, Lde/robv/android/xposed/callbacks/XC_LoadPackage$LoadPackageParam;->packageName:Ljava/lang/String;
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :done
    :try_start
    const-string v0, "com.android.quickstep.AutomationRepositoryImpl"
    const/4 v1, 0x0
    iget-object v2, p1, Lde/robv/android/xposed/callbacks/XC_LoadPackage$LoadPackageParam;->classLoader:Ljava/lang/ClassLoader;
    invoke-static {v0, v1, v2}, Ljava/lang/Class;->forName(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;
    move-result-object v0
    new-instance v1, Ldev/henry/pixellauncher/compat/AutomationFallback;
    invoke-direct {v1}, Ldev/henry/pixellauncher/compat/AutomationFallback;-><init>()V
    invoke-static {v0, v1}, Lde/robv/android/xposed/XposedBridge;->hookAllConstructors(Ljava/lang/Class;Lde/robv/android/xposed/XC_MethodHook;)Ljava/util/Set;
    const-string v0, "com.google.android.apps.nexuslauncher.allapps.n3"
    const/4 v1, 0x0
    invoke-static {v0, v1, v2}, Ljava/lang/Class;->forName(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;
    move-result-object v0
    const-string v1, "run"
    new-instance v3, Ldev/henry/pixellauncher/compat/SearchFallback;
    invoke-direct {v3}, Ldev/henry/pixellauncher/compat/SearchFallback;-><init>()V
    invoke-static {v0, v1, v3}, Lde/robv/android/xposed/XposedBridge;->hookAllMethods(Ljava/lang/Class;Ljava/lang/String;Lde/robv/android/xposed/XC_MethodHook;)Ljava/util/Set;
    const-string v0, "com.android.systemui.shared.recents.model.Task"
    const/4 v1, 0x0
    invoke-static {v0, v1, v2}, Ljava/lang/Class;->forName(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;
    move-result-object v0
    const-string v1, "from"
    new-instance v3, Ldev/henry/pixellauncher/compat/TaskFallback;
    invoke-direct {v3}, Ldev/henry/pixellauncher/compat/TaskFallback;-><init>()V
    invoke-static {v0, v1, v3}, Lde/robv/android/xposed/XposedBridge;->hookAllMethods(Ljava/lang/Class;Ljava/lang/String;Lde/robv/android/xposed/XC_MethodHook;)Ljava/util/Set;
    const-string v0, "com.android.systemui.shared.recents.ISystemUiProxy$Stub$Proxy"
    const/4 v1, 0x0
    invoke-static {v0, v1, v2}, Ljava/lang/Class;->forName(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;
    move-result-object v0
    new-instance v3, Ldev/henry/pixellauncher/compat/OverviewFallback;
    invoke-direct {v3}, Ldev/henry/pixellauncher/compat/OverviewFallback;-><init>()V
    const-string v1, "onOverviewShown"
    invoke-static {v0, v1, v3}, Lde/robv/android/xposed/XposedBridge;->hookAllMethods(Ljava/lang/Class;Ljava/lang/String;Lde/robv/android/xposed/XC_MethodHook;)Ljava/util/Set;
    const-string v1, "onOverviewHidden"
    invoke-static {v0, v1, v3}, Lde/robv/android/xposed/XposedBridge;->hookAllMethods(Ljava/lang/Class;Ljava/lang/String;Lde/robv/android/xposed/XC_MethodHook;)Ljava/util/Set;
    const-string v0, "PixelLauncherCompat: automation, search, TaskInfo and legacy overview fallbacks installed"
    invoke-static {v0}, Lde/robv/android/xposed/XposedBridge;->log(Ljava/lang/String;)V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :error
    goto :done
    :error
    move-exception v0
    invoke-static {v0}, Lde/robv/android/xposed/XposedBridge;->log(Ljava/lang/Throwable;)V
    :done
    return-void
.end method
''', encoding='utf-8')
(SRC / 'AutomationFallback.smali').write_text('''.class public Ldev/henry/pixellauncher/compat/AutomationFallback;
.super Lde/robv/android/xposed/XC_MethodHook;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Lde/robv/android/xposed/XC_MethodHook;-><init>()V
    return-void
.end method

.method protected beforeHookedMethod(Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;)V
    .locals 3
    iget-object v0, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->args:[Ljava/lang/Object;
    array-length v1, v0
    const/4 v2, 0x4
    if-ne v1, v2, :done
    const/4 v1, 0x1
    const/4 v2, 0x0
    aput-object v2, v0, v1
    const-string v0, "PixelLauncherCompat: optional computer-control integration disabled"
    invoke-static {v0}, Lde/robv/android/xposed/XposedBridge;->log(Ljava/lang/String;)V
    :done
    return-void
.end method
''', encoding='utf-8')
(SRC / 'SearchFallback.smali').write_text('''.class public Ldev/henry/pixellauncher/compat/SearchFallback;
.super Lde/robv/android/xposed/XC_MethodHook;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Lde/robv/android/xposed/XC_MethodHook;-><init>()V
    return-void
.end method

.method protected beforeHookedMethod(Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;)V
    .locals 2
    iget-object v0, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->thisObject:Ljava/lang/Object;
    const-string v1, "e"
    invoke-static {v0, v1}, Lde/robv/android/xposed/XposedHelpers;->getObjectField(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    invoke-static {v0, v1}, Lde/robv/android/xposed/XposedHelpers;->getObjectField(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    if-nez v0, :done
    const/4 v0, 0x0
    invoke-virtual {p1, v0}, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->setResult(Ljava/lang/Object;)V
    const-string v0, "PixelLauncherCompat: absent SearchUiManager session skipped"
    invoke-static {v0}, Lde/robv/android/xposed/XposedBridge;->log(Ljava/lang/String;)V
    :done
    return-void
.end method
''', encoding='utf-8')
task_fallback = '''.class public Ldev/henry/pixellauncher/compat/TaskFallback;
.super Lde/robv/android/xposed/XC_MethodHook;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Lde/robv/android/xposed/XC_MethodHook;-><init>()V
    return-void
.end method

.method protected beforeHookedMethod(Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;)V
    .locals 8
    iget-object v0, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->args:[Ljava/lang/Object;
    array-length v1, v0
    const/4 v2, 0x3
    if-ne v1, v2, :done
    const/4 v1, 0x1
    aget-object v2, v0, v1
    check-cast v2, Landroid/app/TaskInfo;
    # Use the native path if the framework has the field expected by this APK.
    :field_start
    const-class v3, Landroid/app/TaskInfo;
    const-string v4, "isRealActivityAppLockEnabled"
    invoke-virtual {v3, v4}, Ljava/lang/Class;->getField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    :field_end
    .catch Ljava/lang/NoSuchFieldException; {:field_start .. :field_end} :adapt
    goto :done
    :adapt
    move-exception v3
    iget-object v3, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->method:Ljava/lang/reflect/Member;
    invoke-interface {v3}, Ljava/lang/reflect/Member;->getDeclaringClass()Ljava/lang/Class;
    move-result-object v3
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v4, 0x0
    aget-object v5, v0, v4
    aput-object v5, v1, v4
    invoke-static {v3, v1}, Lde/robv/android/xposed/XposedHelpers;->newInstance(Ljava/lang/Class;[Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v3
    iget-object v5, v2, Landroid/app/TaskInfo;->taskDescription:Landroid/app/ActivityManager$TaskDescription;
    if-nez v5, :description_ready
    new-instance v5, Landroid/app/ActivityManager$TaskDescription;
    invoke-direct {v5}, Landroid/app/ActivityManager$TaskDescription;-><init>()V
    :description_ready
    const-string v6, "taskDescription"
    invoke-static {v3, v6, v5}, Lde/robv/android/xposed/XposedHelpers;->setObjectField(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/Object;)V
    invoke-virtual {v5}, Landroid/app/ActivityManager$TaskDescription;->getPrimaryColor()I
    move-result v6
    const-string v7, "colorPrimary"
    invoke-static {v3, v7, v6}, Lde/robv/android/xposed/XposedHelpers;->setIntField(Ljava/lang/Object;Ljava/lang/String;I)V
    invoke-virtual {v5}, Landroid/app/ActivityManager$TaskDescription;->getBackgroundColor()I
    move-result v6
    const-string v7, "colorBackground"
    invoke-static {v3, v7, v6}, Lde/robv/android/xposed/XposedHelpers;->setIntField(Ljava/lang/Object;Ljava/lang/String;I)V
    iget-object v5, v2, Landroid/app/TaskInfo;->topActivity:Landroid/content/ComponentName;
    const-string v6, "topActivity"
    invoke-static {v3, v6, v5}, Lde/robv/android/xposed/XposedHelpers;->setObjectField(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/Object;)V
    const/4 v5, 0x2
    aget-object v0, v0, v5
    check-cast v0, Ljava/lang/Boolean;
    invoke-virtual {v0}, Ljava/lang/Boolean;->booleanValue()Z
    move-result v0
    const-string v5, "isLocked"
    invoke-static {v3, v5, v0}, Lde/robv/android/xposed/XposedHelpers;->setBooleanField(Ljava/lang/Object;Ljava/lang/String;Z)V
    iget-object v0, v2, Landroid/app/TaskInfo;->configuration:Landroid/content/res/Configuration;
    iget-object v0, v0, Landroid/content/res/Configuration;->windowConfiguration:Landroid/app/WindowConfiguration;
    invoke-virtual {v0}, Landroid/app/WindowConfiguration;->getAppBounds()Landroid/graphics/Rect;
    move-result-object v0
    const-string v5, "appBounds"
    invoke-static {v3, v5, v0}, Lde/robv/android/xposed/XposedHelpers;->setObjectField(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/Object;)V
    # Apply the APK's own split-screen capability tests via its constant arrays.
    iget-boolean v0, v2, Landroid/app/TaskInfo;->supportsMultiWindow:Z
    if-eqz v0, :dock_ready
    invoke-virtual {v3}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/Class;->getClassLoader()Ljava/lang/ClassLoader;
    move-result-object v0
    const-string v5, "com.android.wm.shell.shared.split.SplitScreenConstants"
    invoke-static {v5, v0}, Lde/robv/android/xposed/XposedHelpers;->findClass(Ljava/lang/String;Ljava/lang/ClassLoader;)Ljava/lang/Class;
    move-result-object v0
    const-string v5, "CONTROLLED_WINDOWING_MODES_WHEN_ACTIVE"
    invoke-static {v0, v5}, Lde/robv/android/xposed/XposedHelpers;->getStaticObjectField(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v5
    check-cast v5, [I
    invoke-virtual {v2}, Landroid/app/TaskInfo;->getWindowingMode()I
    move-result v6
    invoke-static {v5, v6}, Lcom/android/internal/util/ArrayUtils;->contains([II)Z
    move-result v5
    if-eqz v5, :dock_ready
    invoke-virtual {v2}, Landroid/app/TaskInfo;->getActivityType()I
    move-result v6
    if-eqz v6, :dock_true
    const-string v5, "CONTROLLED_ACTIVITY_TYPES"
    invoke-static {v0, v5}, Lde/robv/android/xposed/XposedHelpers;->getStaticObjectField(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v5
    check-cast v5, [I
    invoke-static {v5, v6}, Lcom/android/internal/util/ArrayUtils;->contains([II)Z
    move-result v5
    if-eqz v5, :dock_ready
    :dock_true
    const/4 v4, 0x1
    :dock_ready
    const-string v0, "isDockable"
    invoke-static {v3, v0, v4}, Lde/robv/android/xposed/XposedHelpers;->setBooleanField(Ljava/lang/Object;Ljava/lang/String;Z)V
    # Preserve the ROM's app-lock state instead of defaulting locked apps to unlocked.
    const-string v0, "isTopAppLocked"
    invoke-static {v2, v0}, Lde/robv/android/xposed/XposedHelpers;->getBooleanField(Ljava/lang/Object;Ljava/lang/String;)Z
    move-result v0
    const-string v5, "isAppLockEnabled"
    invoke-static {v3, v5, v0}, Lde/robv/android/xposed/XposedHelpers;->setBooleanField(Ljava/lang/Object;Ljava/lang/String;Z)V
    invoke-virtual {p1, v3}, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->setResult(Ljava/lang/Object;)V
    :done
    return-void
.end method
'''
(SRC / 'TaskFallback.smali').write_text(task_fallback, encoding='utf-8')
(SRC / 'OverviewFallback.smali').write_text('''.class public Ldev/henry/pixellauncher/compat/OverviewFallback;
.super Lde/robv/android/xposed/XC_MethodHook;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Lde/robv/android/xposed/XC_MethodHook;-><init>()V
    return-void
.end method

.method protected beforeHookedMethod(Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;)V
    .locals 5
    iget-object v0, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->method:Ljava/lang/reflect/Member;
    invoke-interface {v0}, Ljava/lang/reflect/Member;->getName()Ljava/lang/String;
    move-result-object v0
    const-string v1, "onOverviewShown"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :finish
    iget-object v0, p1, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->thisObject:Ljava/lang/Object;
    const-string v1, "mRemote"
    invoke-static {v0, v1}, Lde/robv/android/xposed/XposedHelpers;->getObjectField(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/os/IBinder;
    invoke-static {}, Landroid/os/Parcel;->obtain()Landroid/os/Parcel;
    move-result-object v1
    const-string v2, "com.android.systemui.shared.recents.ISystemUiProxy"
    invoke-virtual {v1, v2}, Landroid/os/Parcel;->writeInterfaceToken(Ljava/lang/String;)V
    const/4 v2, 0x0
    invoke-virtual {v1, v2}, Landroid/os/Parcel;->writeBoolean(Z)V
    const/4 v2, 0x7
    const/4 v3, 0x0
    const/4 v4, 0x1
    :tx_start
    invoke-interface {v0, v2, v1, v3, v4}, Landroid/os/IBinder;->transact(ILandroid/os/Parcel;Landroid/os/Parcel;I)Z
    :tx_end
    .catchall {:tx_start .. :tx_end} :recycle_error
    invoke-virtual {v1}, Landroid/os/Parcel;->recycle()V
    goto :finish
    :recycle_error
    move-exception v0
    invoke-virtual {v1}, Landroid/os/Parcel;->recycle()V
    throw v0
    :finish
    const/4 v0, 0x0
    invoke-virtual {p1, v0}, Lde/robv/android/xposed/XC_MethodHook$MethodHookParam;->setResult(Ljava/lang/Object;)V
    return-void
.end method
''', encoding='utf-8')
assets = OUT / 'decoded/assets'
assets.mkdir(exist_ok=True)
(assets / 'xposed_init').write_text('dev.henry.pixellauncher.compat.Entry\n', encoding='utf-8')
run('java', '-jar', ROOT / 'tools/apktool.jar', 'b', OUT / 'decoded', '-o', OUT / 'hook-unsigned.apk')
run('java', '-jar', ROOT / 'tools/uber-apk-signer.jar', '--apks', OUT / 'hook-unsigned.apk', '--out', OUT / 'signed', '--allowResign')
