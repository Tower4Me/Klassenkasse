# Klassenkasse

Klassenkassen-Verwaltung für Lehrkräfte. Verwaltet Schüler, Zahlungsstatus, geplante Ausgaben und Notizen. Läuft als Tray-App unter Windows ohne sichtbares CMD-Fenster.

## Voraussetzungen

- Windows 10 oder neuer
- Python 3.10 oder neuer → https://www.python.org/downloads/

## Installation

```bash
pip install -r requirements.txt
```

## Starten

**Ohne CMD-Fenster (empfohlen):**
```
klassenkasse.pyw
```
Doppelklick im Explorer, oder Rechtsklick → "Öffnen mit pythonw.exe".

**Mit CMD-Fenster (zum Debuggen):**
```bash
python klassenkasse.py
```

## Funktionen

- **Kassenstand** – zeigt eingesammelte Summe, offene Beträge und Zähler bezahlt/gesamt
- **Schülerliste** – Checkboxen für Zahlungsstatus, individueller Betrag pro Schüler
- **Alle auswählen** – Checkbox im Header wählt alle Schüler gleichzeitig aus
- **Betrag ändern** – direkt in der Zeile, Enter oder OK bestätigen
- **CSV Import/Export** – Format: Spalten `name`, `betrag` (optional), Semikolon-getrennt
- **Eventplan** – geplante Ausgaben mit Datum und Kosten, Restbetrag (Kasse minus Ausgaben) wird farbig angezeigt
- **Notizen** – freies Textfeld, Strg+S zum Speichern
- **Tray-Icon** – Fenster schließen minimiert in den System-Tray; Rechtsklick → Öffnen / Beenden

## Dateien

| Datei               | Beschreibung                                          |
|---------------------|-------------------------------------------------------|
| `klassenkasse.pyw`  | Start ohne CMD-Fenster (Windows)                      |
| `klassenkasse.py`   | Identisch, Start mit CMD-Fenster (Debugging)          |
| `klassenkasse.db`   | SQLite-Datenbank (wird beim ersten Start erstellt)    |
| `klassenkasse.log`  | Fehlerprotokoll (wird nur bei Fehlern beschrieben)    |
| `requirements.txt`  | Python-Abhängigkeiten                                 |

## CSV-Import Format

Die CSV-Datei muss mindestens eine Spalte `name` enthalten. Die Spalte `betrag` ist optional.

```csv
name,betrag
Max Mustermann,10.00
Erika Beispiel,10.00
```

Fehlende oder ungültige Beträge werden automatisch auf 10,00 € gesetzt.
