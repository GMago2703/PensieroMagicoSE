#!/bin/bash
# Prova dell'APK su emulatore Android (GitHub Actions): installa, avvia in modalità autotest,
# attende l'esito scritto dall'app nel log e salva schermate e log in emu/.
PKG=it.gmago2703.pensieromagico
mkdir -p emu
adb install -r PensieroMagico.apk || exit 1
adb logcat -c
adb shell am start -n $PKG/org.kivy.android.PythonActivity --es autotest 1
sleep 30
adb exec-out screencap -p > emu/01_avvio.png
esito=""
for i in $(seq 1 120); do
  sleep 5
  if adb logcat -d | grep -q "AUTOTEST FINE OK"; then esito=ok; break; fi
  if adb logcat -d | grep -q "AUTOTEST ERRORE"; then esito=errore; break; fi
  if [ -z "$(adb shell pidof $PKG)" ]; then esito=chiusa; break; fi
done
sleep 8
adb exec-out screencap -p > emu/02_dopo_autotest.png
adb logcat -d > emu/logcat.txt
echo "===== righe AUTOTEST ====="
grep "AUTOTEST" emu/logcat.txt
echo "esito: ${esito:-tempo scaduto}"
if [ "$esito" != ok ]; then
  echo "===== log python ====="
  grep -iE "python|Traceback|Error|FATAL|AndroidRuntime" emu/logcat.txt | tail -150
  exit 1
fi
