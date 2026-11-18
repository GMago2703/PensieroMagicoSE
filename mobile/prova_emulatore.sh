#!/bin/bash
# Prova dell'APK su emulatore Android (GitHub Actions).
# Se c'è Precedente.apk (l'ultima versione firmata pubblicata): la installa, la usa (scarica gli archivi),
# poi installa SOPRA la nuova versione e controlla che l'archivio sia ancora presente (aggiornamento senza
# perdita di dati). Poi la prova normale: autotest con archivi veri, schermate e log in emu/.
PKG=it.gmago2703.pensieromagico
mkdir -p emu

autotest() {   # $1 = nome della fase; scrive emu/logcat_$1.txt e restituisce 0 se "AUTOTEST FINE OK"
  adb logcat -c
  adb shell am start -n $PKG/org.kivy.android.PythonActivity --es autotest 1
  sleep 30
  adb exec-out screencap -p > "emu/01_avvio_$1.png"
  local esito=""
  for i in $(seq 1 180); do
    sleep 5
    if adb logcat -d | grep -q "AUTOTEST FINE OK"; then esito=ok; break; fi
    if adb logcat -d | grep -q "AUTOTEST ERRORE"; then esito=errore; break; fi
    if [ -z "$(adb shell pidof $PKG)" ]; then esito=chiusa; break; fi
  done
  sleep 8
  adb exec-out screencap -p > "emu/02_dopo_autotest_$1.png"
  adb logcat -d > "emu/logcat_$1.txt"
  echo "===== $1: righe AUTOTEST ====="
  grep "AUTOTEST" "emu/logcat_$1.txt"
  echo "$1 esito: ${esito:-tempo scaduto}"
  if [ "$esito" != ok ]; then
    grep -iE "python|Traceback|Error|FATAL|AndroidRuntime" "emu/logcat_$1.txt" | tail -150
    return 1
  fi
  adb shell am force-stop $PKG
  return 0
}

if [ -f Precedente.apk ]; then
  echo "### Prova di aggiornamento: versione precedente, poi la nuova sopra"
  adb install Precedente.apk || exit 1
  autotest precedente || exit 1
  adb install -r PensieroMagico.apk || { echo "AGGIORNAMENTO RIFIUTATO (firma diversa o versione più vecchia)"; exit 1; }
  autotest aggiornata || exit 1
  # dopo l'aggiornamento l'archivio deve esserci già: quasi nessuna estrazione nuova da scaricare
  nuove=$(grep -o "AUTOTEST SE archivio: [0-9]* estrazioni (+[0-9]*)" emu/logcat_aggiornata.txt | grep -o "(+[0-9]*)" | tr -d '(+)')
  echo "Estrazioni SE scaricate dopo l'aggiornamento: ${nuove:-?}"
  if [ -z "$nuove" ] || [ "$nuove" -gt 50 ]; then echo "I DATI NON SONO STATI CONSERVATI"; exit 1; fi
  echo "Aggiornamento riuscito: archivio conservato."
  cp emu/logcat_aggiornata.txt emu/logcat.txt
else
  adb install -r PensieroMagico.apk || exit 1
  autotest nuova || exit 1
  cp emu/logcat_nuova.txt emu/logcat.txt
fi
