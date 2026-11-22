# kit-spec-propagation Specification

## Purpose
Keep the kit's openspec requirements visible to agents working inside each spec store by propagating a copy of the kit `openspec/` folder into every store, so recon flows can consult the rules where the work happens.

## Requirements

### Requirement: Kit openspec copy present in every store
Every store bootstrapped from this kit SHALL carry a verbatim copy of the
kit's `openspec/` folder at `<store>/recon/openspec/`; the copy is
read-only in the store — requirement changes happen in the kit repo (via
PR), never by editing the store's copy.

#### Scenario: Bootstrap placement
- **WHEN** a new store is bootstrapped (RUNBOOK §1 step 5)
- **THEN** the kit's `openspec/` folder is copied to `<store>/recon/openspec/`
  before the store's first push

#### Scenario: Refresh on kit sync
- **WHEN** a store re-syncs its kit scripts/templates to a new kit version
- **THEN** `recon/openspec/` is re-copied verbatim and the store ledger
  records the kit version + copy date

#### Scenario: Store copy never diverges
- **WHEN** an audit diffs `<store>/recon/openspec/` against the kit tree at
  the recorded kit version
- **THEN** the diff is empty (any divergence is corrected by re-copying from
  the kit, not by editing either side ad hoc)

### Requirement: Copy refreshed whole; PIN currency owned by the kit
Refreshes of `<store>/recon/openspec/` SHALL be wholesale, verbatim
replacements of the folder from the kit tree; nothing inside the copy —
including the `PIN:` line of `openspec/project.md` — SHALL ever be edited
store-side. PIN currency is a kit-side duty: the kit SHALL update the
`PIN:` line at every `openspec archive` with a follow-up one-line commit
naming the archive commit, so later copies inherit a fresh reference;
stores record kit versions in their own ledgers, not in the copy.

#### Scenario: Refresh replaces, never patches
- **WHEN** a store refreshes its kit copy
- **THEN** the whole `recon/openspec/` folder is replaced verbatim from the
  kit tree and the store ledger records the kit version + copy date —
  zero edits inside the copy

#### Scenario: Archive advances the kit-side PIN
- **WHEN** `openspec archive` lands on kit main
- **THEN** the same flow commits the one-line follow-up updating the
  `PIN:` line in the kit's own `openspec/project.md` to that archive
  commit — copy audits stay empty because stores copy verbatim
