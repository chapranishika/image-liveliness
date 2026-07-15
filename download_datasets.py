"""
download_datasets.py
Downloads CelebA-Spoof and CFP dataset samples via kagglehub.

IMPORTANT — read before running:
The official full CelebA-Spoof mirror on Kaggle
(attentionlayer241/celeba-spoof-for-face-antispoofing) is approximately 77GB
across 1.1 million files. kagglehub downloads the ENTIRE dataset — there is
no partial/selective download. Downloading 77GB just to sample 300-500
images is not practical for this project.

Two better options, in order of preference:
    1. Use a smaller, pre-curated mirror instead, e.g.
       "trainingdatapro/celeba-spoof-dataset" or "mabdullahsajid/celeba-spoofing"
       — check their actual file count/size on kaggle.com before committing,
       sizes were not confirmed at the time this script was written.
    2. If you specifically need the official full dataset's richer 43-attribute
       labels, download it once on a machine with enough disk space (77GB+
       free), then copy only your sampled subset into data/celeba_spoof_sample/
       and delete the rest — do not keep the full 77GB in your project folder.

CFP's Kaggle mirror (chinafax/cfpw-dataset) is small and fine to download
in full.

Before running this, set up your Kaggle API token:
    1. Go to kaggle.com -> your profile -> Account -> "Create New API Token"
    2. This downloads kaggle.json
    3. Place it at ~/.kaggle/kaggle.json (Mac/Linux) or
       C:\\Users\\<you>\\.kaggle\\kaggle.json (Windows)

Usage:
    python download_datasets.py --celeba-spoof small   # recommended default
    python download_datasets.py --celeba-spoof full     # only if you have 80GB+ free
    python download_datasets.py --skip-celeba-spoof      # just get CFP for now
"""
import kagglehub
import os
import argparse

# Verify these slugs and their actual sizes on kaggle.com before running —
# Kaggle mirrors occasionally get renamed, removed, or re-owned.
CELEBA_SPOOF_SLUGS = {
    "full": "attentionlayer241/celeba-spoof-for-face-antispoofing",   # ~77GB, 1.1M files — official, full
    "small": "trainingdatapro/celeba-spoof-dataset",                   # smaller curated mirror — verify size first
}
CFP_SLUG = "chinafax/cfpw-dataset"  # confirmed small, safe to download in full


def download(dataset_slug, dest_folder, label):
    print(f"Downloading {label} ({dataset_slug}) ...")
    path = kagglehub.dataset_download(dataset_slug)
    print(f"Downloaded to cache: {path}")
    os.makedirs(dest_folder, exist_ok=True)
    print(f"Dataset available at: {path}")
    print(f"NOTE: copy or sample the specific files/folders you want into {dest_folder}")
    print("Do not keep the full dataset inside your project folder if it is large — sample and delete.\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--celeba-spoof", choices=["small", "full"], default="small",
                         help="Which CelebA-Spoof mirror to use. 'small' is strongly recommended (default).")
    parser.add_argument("--skip-celeba-spoof", action="store_true",
                         help="Skip CelebA-Spoof entirely and only download CFP.")
    args = parser.parse_args()

    print("=" * 60)
    print("Dataset Download — CelebA-Spoof and CFP")
    print("=" * 60)

    if not args.skip_celeba_spoof:
        if args.celeba_spoof == "full":
            print("WARNING: 'full' is ~77GB. Confirm you have enough free disk space before continuing.")
            confirm = input("Type YES to continue with the full 77GB download, anything else to cancel: ")
            if confirm != "YES":
                print("Cancelled. Re-run with --celeba-spoof small instead.")
                exit()
        slug = CELEBA_SPOOF_SLUGS[args.celeba_spoof]
        download(slug, os.path.join("data", "celeba_spoof_sample"), "CelebA-Spoof")
    else:
        print("Skipping CelebA-Spoof as requested.")

    download(CFP_SLUG, os.path.join("data", "cfp_sample"), "CFP")

    print("Done. Remember to sample a balanced subset rather than keeping the full dataset in your project folder.")
