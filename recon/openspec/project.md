# Project: recon-spec-store-kit

The kit repo's OWN requirements. These are process requirements for stores
built from this kit — NOT a reconstruction spec of any source repo (those
live in each store's own `openspec/`).

A copy of this entire `openspec/` folder is placed at
`<store>/recon/openspec/` in every x-spec-store (capability
`kit-spec-propagation`) so agents are aware of these requirements when
performing recon on a store. The store's root-level `openspec/` remains the
store's spec store; `recon/openspec/` is a read-only copy of the kit — do
not edit, add, or delete any file inside it, including this one. Refresh
means replacing the WHOLE folder verbatim from the kit tree and recording
the kit version + copy date in the store ledger — never touching the copy.

PIN: kit main @ 52b1cda (2026-11-22). Maintained KIT-side: the kit updates
this line at every `openspec archive` (a follow-up one-line commit naming
the archive commit), so a copy taken from a fresh main always carries a
current reference. A stale PIN relative to the kit's archive history means
this copy predates shipped specs — the fix is a whole-folder re-copy from
the kit, never an edit of this line in the store.
