# Démarrage rapide (français)

## Lancer l'application

**Windows** — double-clique sur `start.bat`. Il installe la dépendance optionnelle, démarre le
service et ouvre le navigateur sur http://localhost:8642/m.

**En ligne de commande** :

```bash
python app/server.py --demo     # fausses alertes, aucun token nécessaire
python app/server.py            # données réelles (voir config.json)
```

## Configuration

Au premier lancement, `config.json` est créé à partir de `config.example.json`. Ce fichier contient
les tokens : il n'est **jamais** envoyé sur GitHub (il est dans `.gitignore`).

Pour les données réelles, demande un token gratuit sur <https://alerts.in.ua/api-request> et
colle-le dans `"alerts_in_ua_token"`. Sans token, l'app utilise le miroir ubilling (niveau oblast
uniquement) et les canaux Telegram publics, qui donnent déjà l'essentiel.

Les réglages utiles sont documentés dans le tableau du [README](../README.md#configuration).

## Ouvrir le projet dans VS Code

```bash
code .
```

- **F5** lance l'app en mode démo.
- **Ctrl+Shift+B** : lancer, démo, tests, lint, déployer.
- Le panneau *Testing* est branché sur pytest.
- Les extensions recommandées (Python, Ruff, Docker) sont proposées à la première ouverture.

## Déployer

```bash
fly deploy
```

Ou double-clique sur `deploy-fly.bat`. Détails et dépannage : [DEPLOY.md](DEPLOY.md).

**Si un déploiement ne change rien** : compare le tag de build en bas du panneau « Plus » (⋯) de l'app
(`build AAAA-MM-JJ HH:MM UTC`) avec celui dans `static/kyiv.html`. S'ils diffèrent, les fichiers
déployés ne sont pas ceux que tu as modifiés — `git status` et `git log -1` te disent quelle version
est réellement partie.

## Envoyer sur GitHub

```bash
git add -A
git commit -m "ce que tu as changé"
git push
```

Première fois, ou si tu préfères un clic : `scripts\github-push.bat` (nécessite GitHub CLI —
`winget install GitHub.cli`).

## Modifier l'interface

Tout le front est dans `static/kyiv.html` (une seule page) et `static/i18n.js` (les textes en trois
langues). Après une modification de l'interface, pense à monter le `build …` du panneau « Plus » : c'est ce
qui te permet de vérifier d'un coup d'œil que la version déployée est la bonne.

Avant de toucher à `app/`, lis [ARCHITECTURE.md](ARCHITECTURE.md), et surtout
[SAFETY.md](SAFETY.md) : les règles sur les trajectoires, les cibles périmées et les bannières
d'alerte ne sont pas des préférences de style.
