# SmokeWatch Canada

[![CI](https://github.com/omarfaruqe/smokewatch-canada/actions/workflows/ci.yml/badge.svg)](https://github.com/omarfaruqe/smokewatch-canada/actions/workflows/ci.yml)

**[English version](README.md)**

Plateforme d'ingénierie des données à l'échelle nationale qui suit les feux de forêt, la fumée
et la qualité de l'air dans toutes les provinces et tous les territoires du Canada, et estime
chaque jour la population exposée à un air à risque élevé.

## Sources de données

| Source | Éditeur | Contenu | Fréquence |
|---|---|---|---|
| Points chauds du SCIFV | Ressources naturelles Canada | Détections satellitaires de feux | Quotidienne |
| Périmètres du SCIFV | Ressources naturelles Canada | Périmètres actuels (historique SCD2) et finaux des saisons passées | Quotidienne / annuelle |
| GeoMet du SMC | Environnement et Changement climatique Canada | Cote air santé (CAS) observée et prévue, météo horaire | Horaire |
| Archives du SNPA | Environnement et Changement climatique Canada | PM2,5, O3 et NO2 horaires par station (CAS historique calculée) | Annuelle |
| Recensement de 2021 | Statistique Canada | Limites des divisions de recensement et des provinces, population | Statique |

## Architecture

Extracteurs Python → couche bronze S3 (SeaweedFS, manifestes sha256) → chargements
incrémentaux par `COPY` dans Postgres + PostGIS (`raw`) → modèles dbt (`staging`, `marts`)
→ API FastAPI et tableau de bord cartographique bilingue. Dagster orchestre l'ensemble
(horaires, reprises, contrôles de fraîcheur) et GitHub Actions vérifie chaque modification.
Voir le diagramme dans la [version anglaise](README.md#architecture).

## Démarrage rapide

```bash
cp .env.example .env                 # puis modifier les mots de passe
docker compose up -d                 # Postgres+PostGIS (5433), SeaweedFS S3 (8333)
uv venv --python 3.13 .venv && source .venv/bin/activate
uv pip install -e ".[dev,dbt,orchestration,api]"
pytest -q
```

## Orchestration, API et tableau de bord

```bash
export DAGSTER_HOME="$PWD/.dagster" && dagster dev     # http://localhost:3000
uvicorn smokewatch.api.main:app --port 8000            # http://localhost:8000
```

- Tâche horaire `hourly_air_quality` (CAS) et tâche quotidienne `daily_pipeline` à 7 h 35
- Tableau de bord : carte des divisions de recensement selon la CAS maximale du jour, points
  chauds, périmètres de 2023, relecture de la saison et graphique de l'exposition
- Documentation de l'API : http://localhost:8000/docs

## Saison 2023 : validation

- CAS calculée de 15 à 17 dans la région de Montréal le 25 juin 2023
- Pic des points chauds en juin au Québec et en août dans les Territoires du Nord-Ouest
- 16,0 millions d'hectares de périmètres pour l'ensemble du Canada
- Jusqu'à 15,4 millions de personnes dans des divisions où l'air était à risque élevé
  (30 juin 2023)

## Méthode et limites

L'exposition est estimée par division de recensement de 2021 : si un lieu de mesure de la CAS
d'une division atteint un risque élevé (CAS arrondie de 7 ou plus) au cours d'une journée
(UTC), toute la population de la division est comptée. Les totaux sont donc des bornes
supérieures. Les périmètres du SCIFV sont des estimations fondées sur les points chauds, et
non des tracés cartographiés par les agences.

## Licence

Code : MIT. Données : contient des informations visées par la
[Licence du gouvernement ouvert – Canada](https://ouvert.canada.ca/fr/licence-du-gouvernement-ouvert-canada).
