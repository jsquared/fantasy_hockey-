name: Update Fantasy Analysis

permissions:
  contents: write

on:
  workflow_dispatch:  # allows manual run

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      # 1️⃣ Checkout the repo
      - uses: actions/checkout@v4

      # 2️⃣ Setup Python
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # 3️⃣ Install dependencies
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install yahoo_oauth yahoo-fantasy-api requests

      # 4️⃣ Write Yahoo OAuth file from secret
      - name: Write Yahoo OAuth file
        run: |
          echo '${{ secrets.YAHOO_OAUTH_JSON }}' > oauth2.json

      # 5️⃣ Run your analysis script
      - name: Run analyze_team.py
        run: python analyze_team.py

      # 6️⃣ Commit and push analysis.json
      - name: Commit and push analysis.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"
          git add docs/team_analysis.json
          git diff --cached --quiet || git commit -m "Update team_analysis.json"
          git push origin HEAD
