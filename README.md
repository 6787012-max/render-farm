# render-farm
Free remote rendering for our own HTML/canvas scenes (GitHub Actions). Jobs arrive XOR-scrambled on branch `in/<job>`,
results go back on `out/<job>`; the local client (`remote_render.py`) deletes both branches when done.
Fonts in `fonts/` are SIL Open Font License (Heebo, Secular One, Suez One, Frank Ruhl Libre, David Libre, Assistant).
