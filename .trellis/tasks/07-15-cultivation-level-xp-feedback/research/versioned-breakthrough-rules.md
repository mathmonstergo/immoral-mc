# Versioned breakthrough-rule architecture

## Question

Should spirit-root aptitude and major-breakthrough behavior be stored as a new
database field, hardcoded in service code, or represented another way?

## Existing constraints

* `life_spirit_roots` already stores immutable `quality_code`, canonical
  `base_element_codes`, and `generator_version`.
* Root count is an existing fact: it is the cardinality of
  `base_element_codes`; `variant` and `celestial` are valid one-root cases.
* Database design deliberately avoided inventing breakthrough-potential fields
  before their semantics existed.
* The combat module already uses a validated, version-controlled JSON catalog
  loaded into immutable typed definitions.
* Cultivation probabilities are intended to use integer basis points rather
  than floating point.

## Options

### Redundant aptitude column

Add a mutable or frozen numeric aptitude score to each life. This makes queries
simple but duplicates information derived from spirit-root facts, needs a
migration whenever semantics change, and risks disagreement between the root
and score.

### Realm-specific hardcoded branches

Write conditions such as `if root_count <= 3` directly in the breakthrough
service. This is initially quick but mixes content balance, probability curves,
failure transitions, and transaction orchestration. Later realm rules would
grow a brittle conditional tree.

### Versioned rule catalog plus persisted attempt snapshot (recommended)

Keep the immutable spirit root as the source fact. A typed, validated catalog
maps facts and attempt inputs to an outcome profile. Generic service code:

1. derives root count from the immutable root;
2. selects a breakthrough rule and root profile;
3. validates level, full progress, pills, and active-session constraints;
4. calculates success in integer basis points;
5. atomically consumes items and creates a persisted session;
6. stores the rule/version and all decision inputs/outputs needed for audit;
7. settles the frozen session idempotently after its duration.

An in-progress session is unaffected by catalog edits because it stores a
decision snapshot such as:

* stable rule ID and schema/content version or hash;
* source/target level and failure target/mode;
* spirit-root quality and derived root count snapshot;
* consumed pill count;
* frozen success basis points and random roll/result policy;
* start, completion, status, outcome, and idempotency key.

The database stores player facts, item ledger entries, sessions, and outcomes;
the committed catalog stores balance rules. The application code contains only
the bounded rule vocabulary, validation, transactions, and settlement state
machine.

## Recommended initial catalog shape

Use a committed JSON catalog, following `combat/mythicmob_rewards.json`, with
typed immutable loader classes. The 练气 -> 筑基 rule should include:

* eligible source levels `10..13` and target level `14`;
* requirement `current_progress_full`;
* duration bounds `600..900` seconds;
* required item code `foundation_establishment_pill`;
* root-count profiles for `1..3`, `4`, and `5`;
* pill-count-to-success-basis-points curves;
* failure transition `advance_one_level` for source levels `10..12`;
* failure transition `stay_full` for source level `13`.

Avoid a fully generic expression language in the MVP. Typed fields and a small
closed set of failure modes are easier to validate, test, and migrate.

## Recommendation

Do not add a general aptitude field and do not hardcode the balance table.
Derive root count from immutable spirit-root facts, configure the breakthrough
rule in a committed versioned catalog, and freeze each attempt's calculated
decision in PostgreSQL.
