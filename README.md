# Mailjet TUI — Dashboard Python

Un dashboard terminal (TUI) pour visualiser, filtrer et analyser vos envois Mailjet, avec support multi-comptes.

---

## Prérequis

- Python 3.9+
- Un compte [Mailjet](https://app.mailjet.com) avec une clé API (facultatif — un mode mock est disponible)

---

## Installation

```bash
# 1. Cloner le dépôt
git clone <url-du-repo>
cd Mailjet_Py

# 2. Créer et activer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

# 3. Installer les dépendances
pip install mailjet-rest textual textual-plotext plotext
```

---

## Lancer l'application

```bash
python app.py
```

La base de données `mailjet_accounts.db` est créée automatiquement au premier lancement.

---

## Ajouter un compte Mailjet

Au premier lancement, l'app démarre en **mode mock** (données aléatoires).

Pour connecter un vrai compte :

1. Récupérez votre **API Key** et **API Secret** sur [app.mailjet.com → Account → API Keys](https://app.mailjet.com/account/api_keys)
2. Dans l'app, cliquez sur **Gérer comptes** dans la sidebar
3. Remplissez le formulaire (Nom, API Key, API Secret) et cliquez **Ajouter**
4. Fermez le modal — le compte est sélectionné automatiquement

Vous pouvez ajouter autant de comptes que nécessaire et basculer entre eux via le sélecteur **Compte actif**.

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Multi-comptes** | Gérez plusieurs comptes Mailjet (ajout, modification, suppression) |
| **Filtres avancés** | Statut, plage de dates, émetteur, destinataire |
| **Tableau des envois** | Date/heure, émetteur, destinataire, statut, sujet |
| **Statistiques** | Répartition par statut (nombre + %) sur la sélection courante |
| **Graphique horaire** | Visualisation des envois par heure (plotext) |
| **Export** | Export CSV ou JSON de la sélection courante |
| **Mode mock** | Données aléatoires si aucun compte configuré |

---

## Raccourcis clavier

| Touche | Action |
|---|---|
| `r` | Rafraîchir les données |
| `q` | Quitter |
| `Échap` | Fermer un modal |

---

## Structure du projet

```
Mailjet_Py/
├── app.py                 # Application TUI principale
├── mailjet_api.py         # Client API Mailjet + mode mock
├── accounts_db.py         # Gestion des comptes (SQLite)
├── mailjet_accounts.db    # Base de données locale (créée auto, ignorée par git)
└── debug_api.py           # Outil de diagnostic API (standalone)
```

---

## Sécurité

Les clés API sont stockées **en clair** dans `mailjet_accounts.db` (fichier local SQLite).
Ce fichier est exclu du dépôt git via `.gitignore` — ne le commitez jamais.
