# kol-tracker

English-only pump.fun KOL tracker. The site files live at the repository root. `.github/workflows/update.yml` refreshes `feed.json` and `data/` every 10 minutes.

Live site: https://kol-tracker.com/

## Enable GitHub Pages

This repository's token cannot change Pages settings. The owner needs to turn the site on once:

1. Open https://github.com/khaledpakr/kol-tracker/settings/pages
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Choose branch **main** and folder **/ (root)**, then save.

After a run pushes `feed.json` or `data/`, the workflow asks GitHub to rebuild the Pages site so the live feed updates.
