# Full flow: download -> update -> keep only *-latest
python /home/louis/repos/ColbertChat/database/run_update.py --cleanup-old-dumps

# Toy test
# python /home/louis/repos/ColbertChat/database/tests/test_update.py

# # Skip download, just update current dumps
# python /home/louis/repos/ColbertChat/database/run_update.py --skip-download

# # Custom data directories
# python /home/louis/repos/ColbertChat/database/run_update.py --data-dirs data/service-public/vosdroits-latest data/service-public/entreprendre-latest

# # Do not cleanup vectors/tracking for files removed from dataset
# python /home/louis/repos/ColbertChat/database/run_update.py --no-cleanup-removed