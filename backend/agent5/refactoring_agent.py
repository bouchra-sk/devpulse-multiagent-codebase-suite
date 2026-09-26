"""
Agent 5 : IBM Bob Refactoring Agent
------------------------------------------------
Prend le code original + le rapport de l'Agent 4 (Security & Quality)
et produit une version corrigée et sécurisée, en jouant le rôle d'un
Senior Software Engineer (Meta-Prompting orienté rôle).
"""

import json
import re

from backend.Agent2.llm_client import call_llm

SYSTEM_PROMPT = """Tu es un Senior Software Engineer spécialisé en sécurité
et en Clean Code. On te donne un extrait de code et un rapport d'audit
listant des problèmes de sécurité et de qualité détectés dessus.

Ta mission :
1. Corriger TOUS les problèmes listés dans le rapport.
2. Garder le comportement fonctionnel du code identique (ne pas ajouter
   de nouvelles fonctionnalités, ne rien retirer qui n'est pas listé).
3. Respecter les principes du Clean Code (nommage clair, fonctions
   courtes, gestion d'erreurs explicite).

Instructions spécifiques pour les problèmes courants :
- SEC001 (SQL injection) : remplace la concaténation/interpolation par des
  requêtes paramétrées. Utilise un tuple de paramètres séparé et passe-le
  à cursor.execute(query, params). Placeholder : `?` (sqlite3) ou `%s`
  (psycopg2/mysql). Ne laisse JAMAIS la variable query_params sans l'utiliser.
- SEC002 (credential hardcodé) : charge la valeur depuis os.getenv("NOM_VAR").
  Ajoute "import os" si absent. NE supprime pas la variable — remplace
  juste la valeur littérale.
- SEC003 (eval/exec) : détermine l'intention réelle du code :
    * Si l'argument est un identifiant numérique (user_id, id, pk…) :
      utilise int(expr) enveloppé dans try/except ValueError.
    * Si l'argument est un littéral Python structuré (liste, dict, tuple) :
      utilise ast.literal_eval(expr).
    * Si l'argument est du JSON : utilise json.loads(expr).
    * N'utilise JAMAIS ast.literal_eval() pour des IDs numériques simples.
    * Ne remplace jamais eval() par un simple commentaire vide.
- SEC004 (hash faible) : remplace md5/sha1 par hashlib.sha256.
- QUAL002 (erreur de syntaxe) : corrige l'erreur de syntaxe signalée sans
  changer le comportement voulu du code (ex. mot-clé `def` tronqué en `ef`).
  Valide que le code résultant est syntaxiquement correct avant de le retourner.

Réponds UNIQUEMENT avec un objet JSON de cette forme, sans texte autour,
sans balises markdown :
{
  "refactored_code": "<le code corrigé complet>",
  "changes_summary": "<résumé en 2-4 phrases des changements effectués>"
}
"""

# ─────────────────────────────────────────────────────────────
# Correctifs déterministes (SANS LLM), utilisés uniquement quand
# IBM Bob 2.0 n'est pas connecté (result["mocked"] is True).
#
# Chaque correctif est sûr par construction : il ne touche QUE les
# lignes explicitement signalées par l'Agent 4 pour la règle
# correspondante, et seulement si la ligne correspond exactement au
# motif attendu pour cette règle. Toute ligne signalée qui ne
# correspond pas au motif reconnu est laissée INCHANGÉE et sa règle
# est reportée dans "remaining_rule_ids" pour traitement par le vrai
# LLM — on ne devine jamais une correction sur un motif qu'on ne
# reconnaît pas avec certitude.
# ─────────────────────────────────────────────────────────────

# SEC002 — identifiant codé en dur : `var = "littéral"` où var ressemble
# à un password / api_key / secret / token.
_HARDCODED_CRED_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)(?P<var>\w*(?:password|passwd|api[_-]?key|secret|token)\w*)'
    r'\s*=\s*[\'"][^\'"]+[\'"]',
    re.IGNORECASE,
)

# SEC001 — injection SQL par concaténation : `var = "littéral" + expr`
# (cas le plus fréquent : une requête SQL construite avec `+`).
_SEC001_CONCAT_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)(?P<var>\w+)\s*=\s*'
    r'(?P<quote>[\'"])(?P<literal>[^\'"]*)(?P=quote)'
    r'\s*\+\s*(?P<expr>\w+(?:\.\w+|\[[^\]]+\])*)\s*$'
)

# SEC003 — appel eval() en affectation directe : `var = eval(expr)`.
_SEC003_EVAL_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)(?P<var>\w+)\s*=\s*eval\(\s*(?P<expr>[^()]+?)\s*\)\s*$'
)

# Noms de variables qui signalent un identifiant numérique plutôt qu'un
# littéral Python structuré. Quand le nom de l'expression contient un de
# ces fragments, int() + ValueError est préféré à ast.literal_eval().
_NUMERIC_ID_FRAGMENTS = frozenset({
    "id", "user_id", "pk", "fk", "record_id", "row_id",
    "item_id", "object_id", "entity_id", "index", "idx",
})

# QUAL002 — mot-clé `def` tronqué en `ef` (erreur de frappe fréquente).
_QUAL002_MISSING_D_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)ef(?P<rest>\s+\w+\s*\([^)]*\)\s*:.*)$'
)


def _auto_fix_all(code: str, findings: list[dict]) -> dict:
    """
    Applique, ligne par ligne, les correctifs déterministes reconnus pour
    SEC001, SEC002, SEC003 et QUAL002.

    Retourne un dict :
      {
        "fixed_code": str,
        "applied": list[str],           # description humaine de chaque fix appliqué
        "remaining_rule_ids": list[str], # règles trouvées mais non corrigées automatiquement
      }

    Les numéros de ligne utilisés pour retrouver un finding correspondent
    TOUJOURS aux numéros de ligne du code ORIGINAL (findings["line"]), même
    si un correctif précédent a inséré des lignes supplémentaires (ex. une
    ligne `xxx_params = (...)` ajoutée après une correction SEC001) : on ne
    relit jamais les positions dans le code déjà modifié.
    """
    findings_by_line: dict[int, list[dict]] = {}
    for f in findings:
        line_no = f.get("line")
        if line_no is None:
            continue
        findings_by_line.setdefault(line_no, []).append(f)

    lines = code.splitlines()
    output_lines: list[str] = []
    applied: list[str] = []
    handled_rule_ids: set[str] = set()
    need_os_import = False
    need_ast_import = False

    for i, line in enumerate(lines, start=1):
        rule_ids_here = {f.get("rule_id") for f in findings_by_line.get(i, [])}
        emitted = False

        if "QUAL002" in rule_ids_here:
            m = _QUAL002_MISSING_D_PATTERN.match(line)
            if m:
                output_lines.append(f'{m.group("indent")}def{m.group("rest")}')
                applied.append(
                    f"Ligne {i} : mot-clé `def` manquant restauré "
                    f"(`ef ...` → `def ...`)."
                )
                handled_rule_ids.add("QUAL002")
                emitted = True

        if not emitted and "SEC002" in rule_ids_here:
            m = _HARDCODED_CRED_PATTERN.match(line)
            if m:
                var_name = m.group("var")
                indent = m.group("indent")
                env_name = var_name.upper()
                output_lines.append(f'{indent}{var_name} = os.getenv("{env_name}")')
                applied.append(
                    f"Ligne {i} : `{var_name}` chargé depuis la variable "
                    f"d'environnement `{env_name}` au lieu d'être codé en dur."
                )
                handled_rule_ids.add("SEC002")
                need_os_import = True
                emitted = True

        if not emitted and "SEC001" in rule_ids_here:
            m = _SEC001_CONCAT_PATTERN.match(line)
            if m:
                indent = m.group("indent")
                var = m.group("var")
                quote = m.group("quote")
                literal = m.group("literal")
                expr = m.group("expr")
                # Émet la requête paramétrée, le tuple de paramètres, ET l'appel
                # cursor.execute() — les trois lignes forment une unité sécurisée.
                # Hypothèse : placeholder `?` (sqlite3). Si le driver est
                # psycopg2/mysql, remplacer `?` par `%s`.
                output_lines.append(f'{indent}{var} = {quote}{literal}?{quote}')
                output_lines.append(f'{indent}{var}_params = ({expr},)')
                output_lines.append(
                    f'{indent}cursor.execute({var}, {var}_params)'
                )
                applied.append(
                    f"Ligne {i} : requête SQL paramétrée — concaténation de "
                    f"`{expr}` remplacée par un placeholder `?` ; paramètres "
                    f"extraits dans `{var}_params` ; appel "
                    f"`cursor.execute({var}, {var}_params)` ajouté. "
                    f"Adapter le placeholder en `%s` si le driver est psycopg2/mysql."
                )
                handled_rule_ids.add("SEC001")
                emitted = True

        if not emitted and "SEC003" in rule_ids_here:
            m = _SEC003_EVAL_PATTERN.match(line)
            if m:
                indent = m.group("indent")
                var = m.group("var")
                expr = m.group("expr").strip()
                expr_lower = expr.lower()

                # Choisit int() pour les identifiants numériques connus,
                # ast.literal_eval() pour tout autre littéral Python.
                is_numeric_id = any(
                    frag in expr_lower for frag in _NUMERIC_ID_FRAGMENTS
                )

                if is_numeric_id:
                    # int() avec gestion d'erreur explicite
                    output_lines.append(f'{indent}try:')
                    output_lines.append(f'{indent}    {var} = int({expr})')
                    output_lines.append(f'{indent}except ValueError as exc:')
                    output_lines.append(
                        f'{indent}    raise ValueError('
                        f'f"Invalid numeric ID: {{{expr}!r}}") from exc'
                    )
                    applied.append(
                        f"Ligne {i} : `eval({expr})` remplacé par "
                        f"`int({expr})` (avec try/except ValueError). "
                        f"Raison : `{expr}` est un identifiant numérique — "
                        f"int() est la conversion sûre et directe."
                    )
                else:
                    output_lines.append(
                        f'{indent}{var} = ast.literal_eval({expr})'
                    )
                    applied.append(
                        f"Ligne {i} : `eval({expr})` remplacé par "
                        f"`ast.literal_eval({expr})`. Raison : l'expression "
                        f"ne correspond pas à un identifiant numérique connu "
                        f"— ast.literal_eval() est utilisé pour parser les "
                        f"littéraux Python sans exécuter de code arbitraire. "
                        f"Si l'intention est un entier simple, utilisez "
                        f"`int({expr})`."
                    )
                    need_ast_import = True

                handled_rule_ids.add("SEC003")
                emitted = True

        if not emitted:
            output_lines.append(line)

    fixed_code = "\n".join(output_lines)

    imports_to_add = []
    if need_os_import and "import os" not in fixed_code:
        imports_to_add.append("import os")
    if need_ast_import and "import ast" not in fixed_code:
        imports_to_add.append("import ast")
    if imports_to_add:
        fixed_code = "\n".join(imports_to_add) + "\n" + fixed_code

    all_rule_ids = {f.get("rule_id", "?") for f in findings}
    remaining_rule_ids = sorted(all_rule_ids - handled_rule_ids)

    return {
        "fixed_code": fixed_code,
        "applied": applied,
        "remaining_rule_ids": remaining_rule_ids,
    }


def _format_findings(findings: list[dict]) -> str:
    if not findings:
        return "Aucun problème détecté par l'Agent 4."

    lines = []
    for f in findings:
        severity = str(f.get("severity", "unknown")).upper()
        rule_id = f.get("rule_id", "UNKNOWN")
        title = f.get("title", "Issue")
        line = f.get("line", "unknown")
        recommendation = f.get("recommendation", "Aucune recommandation fournie.")
        code_snippet = f.get("code", "")
        lines.append(
            f"- [{severity}] {rule_id} — {title} (ligne {line})\n"
            f"  Code concerné : `{code_snippet}`\n"
            f"  Recommandation : {recommendation}"
        )
    return "\n".join(lines)


def _parse_json_response(raw: str) -> dict:
    """
    Extrait le JSON de la réponse du LLM, même si celui-ci l'a entouré
    de ```json ... ``` malgré la consigne.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Réponse du LLM non parsable en JSON : {e}\nRéponse brute : {raw[:300]}"
        )

    if "refactored_code" not in data:
        raise RuntimeError("La réponse du LLM ne contient pas 'refactored_code'.")

    return {
        "refactored_code": data["refactored_code"],
        "changes_summary": data.get("changes_summary", ""),
    }


def refactor_code(code: str, findings: list[dict]) -> dict:
    """
    Orchestration de l'Agent 5.
    Retourne {"refactored_code": str, "changes_summary": str, "mocked": bool}.
    """
    user_prompt = f"""CODE ORIGINAL :
```python
{code}
```

RAPPORT DE L'AGENT 4 (problèmes à corriger) :
{_format_findings(findings)}

Rappel important pour SEC003 (eval/exec) :
  - Analyse ce que le code essaie de faire avec eval().
  - Si l'intention est de convertir une chaîne en entier : utilise int().
  - Si l'intention est de parser du Python littéral : utilise ast.literal_eval().
  - Si l'intention est de parser du JSON : utilise json.loads().
  - Ne mets JAMAIS un simple commentaire à la place de eval() sans fournir
    une vraie alternative fonctionnelle.

Génère maintenant le JSON demandé."""

    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.2)

    if result["mocked"]:
        # Correctifs réels (sans LLM), sûrs et déterministes, pour tous les
        # findings dont la ligne correspond exactement au motif reconnu.
        fix_result = _auto_fix_all(code, findings)
        fixed_code = fix_result["fixed_code"]
        applied_fixes = fix_result["applied"]
        remaining_rule_ids = fix_result["remaining_rule_ids"]

        summary_lines = [""]
        if applied_fixes:
            summary_lines.append("")
            summary_lines.append("")
        if remaining_rule_ids:
            summary_lines.append(
                ""
                f"{', '.join(remaining_rule_ids)}."
            )
        if not applied_fixes and not remaining_rule_ids:
            summary_lines.append("Aucun problème à corriger.")

        return {
            "refactored_code": fixed_code,
            "changes_summary": "\n".join(summary_lines),
            "mocked": True,
        }

    parsed = _parse_json_response(result["content"])
    parsed["mocked"] = False
    return parsed