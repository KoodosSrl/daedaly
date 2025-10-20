# Daedaly (Odoo 18)

Modulo Odoo che unifica configurazioni IA e funzionalità di supporto ai progetti e alle task. Consente di:
- Configurare il provider GPT (OpenAI o Gemini) e testare la connessione/credito.
- Allegare documentazione (PDF) ai progetti e alle task, con estrazione testo via PyMuPDF (fitz).
- Generare un’analisi completa del progetto (Descrizione, Note Economiche, Criticità) in base al framework di PM selezionato.
- Generare le attività (task) a partire dalla documentazione, con strutture e tag coerenti al framework scelto (PRINCE2, Agile, Agile‑Scrum, Lean).
- Supportare funzioni AI anche a livello di singola task (descrizione e to‑do).

## Requisiti
- Odoo 18 con modulo `project` installato.
- Dipendenze Python (sistema):
  - `pymupdf` (import `fitz`) per l’estrazione del testo dai PDF
  - `requests` per la chiamata a un eventuale agente esterno
  - Opzionali in base al provider: `openai`, `google-generativeai`

## Installazione
1. Assicurati che le dipendenze Python siano disponibili nell’ambiente di Odoo.
2. Copia la cartella `daedaly` tra gli addons e aggiorna l’elenco app.
3. Installa “Daedaly”.
4. Verifica di rimuovere eventuali moduli legacy che coprono funzionalità simili prima di installare Daedaly. Le chiavi di configurazione sono state rinominate (usa le nuove chiavi in Impostazioni → Daedaly).

## Configurazione
- Vai su Impostazioni → Daedaly (menu in basso sotto Configurazione).
- Imposta:
  - `What GPT to use`: OpenAI o Gemini
  - Chiavi API: `OpenAI Key` e/o `Gemini Key`
  - `AI Agent URL` (opzionale): endpoint esterno per fallback di analisi documenti (`daedaly.agent_url`)
- Usa i pulsanti “Test GPT API Connection” e “Check API Credit” per verificare connettività/credito.

## Utilizzo nel Progetto
Apri un progetto e troverai la pagina “Documentation”. Qui puoi:
- Aggiungere allegati PDF (estrazione testo automatica per le funzioni AI).
- Selezionare `PM Framework` tra: PRINCE2, Agile, Agile‑Scrum, Lean.
- Pulsanti:
  - `Go Daedaly`: genera un’analisi completa del progetto e compila i campi:
    - Descrizione (campo standard del progetto)
    - Note Economiche (HTML)
    - Criticità (HTML)
    - Tags (creati/associati automaticamente)
  - `Generate Tasks`: genera task secondo il framework selezionato (vedi dettaglio sotto) e assegna tag coerenti (es. “PRINCE2: Initiating”, “Sprint 1”, “Iteration 2”, “Value Stream: Onboarding”, ecc.).

### Prompt dinamico per Analisi Progetto (tasto “Go Daedaly”)
Il contenuto del prompt si adatta a `PM Framework`:
- PRINCE2: enfasi su business case, prodotti, organizzazione, fasi e tolleranze, rischi e cambiamenti.
- Agile‑Scrum: ruoli, backlog, obiettivi di sprint, cerimonie, DoD, dipendenze e rischi.
- Lean: value stream, sprechi (muda), flusso, pull, kaizen, metriche e rischi operativi.
- Agile (generico): valore utente, MVP, backlog tematico/epic, accettazione, roadmap iterativa e rischi.

L’output atteso è JSON con le chiavi: `description`, `economic_notes`, `criticita`, `tags`.

### Prompt dinamico per Generazione Task (tasto “Generate Tasks”)
- PRINCE2 → JSON con `phases[ { phase, tasks[] } ]`
- Agile‑Scrum → JSON con `sprints[ { sprint, tasks[] } ]`
- Lean → JSON con `value_streams[ { stream, tasks[] } ]`
- Agile (default) → JSON con `iterations[ { iteration, tasks[] } ]`

Ogni task deve avere `title` e `description`. Il modulo crea i record `project.task` e assegna tag coerenti alla raggruppa‑zione.

### Lista & Kanban Progetti
- Nella lista progetti è esposto il campo `PM Framework`.
- Nella kanban progetti viene mostrato un badge con `PM Framework`.

## Utilizzo nella Task
All’interno della task troverai due pagine aggiuntive:
- Documentation: per allegare PDF che concorrono al contesto.
- AI Helper: pulsanti
  - `Smart Description`: aggiorna la descrizione della task sulla base dei documenti e della descrizione corrente.
  - `Smart ToDo`: genera una lista operativa (HTML) dei passi da eseguire.

## Modello Dati
- Nuovi modelli:
  - `project.documentation`: documenti associati al progetto (nome, file, data)
  - `task.documentation`: documenti associati alla task (nome, file, data)
- Estensioni su progetto (`project.project`):
  - `pm_framework` (selection)
  - `economic_notes` (Html)
  - `criticita` (Html)
- Estensioni su task (`project.task`):
  - `documentation_ids` (One2many)
  - `todo_html` (Html)

## Sicurezza e Menu
- Sicurezze in `security/ir.model.access.csv` per i modelli aggiunti e il wizard di test.
- Menu Impostazioni: “Daedaly” con azione “Test GPT API Connection”.

## Fallback Agente Esterno
Se le chiamate al provider AI falliscono, il modulo può interrogare un endpoint esterno opzionale (`daedaly.agent_url`, path `/ask`, JSON `{"question": "..."}`). La risposta dovrebbe essere JSON compatibile con gli schemi descritti sopra; in caso contrario, il testo viene gestito come fallback.

## Error Handling e Limitazioni
- Se `pymupdf` (fitz) non è installato, la lettura PDF restituisce un messaggio e limita le funzioni AI basate su documenti.
- Se `openai` o `google-generativeai` non sono installati o le chiavi non sono valide, il test connessione/credito fallirà con un messaggio esplicativo.
- Il parsing JSON è robusto (rileva blocchi json tra backticks o la porzione tra `{` e `}`), ma in caso di output non conforme si ricade su testi grezzi.

## Note di Migrazione
- Le precedenti chiavi config di eventuali soluzioni legacy sono sostituite dalle nuove chiavi `daedaly.*`.
- Disinstalla i vecchi moduli che sovrappongono le stesse funzionalità prima di usare `Daedaly`.

---
Per suggerimenti o estensioni (badge colorati per framework, traduzioni, ulteriori provider), apri una issue o proponi una PR.
