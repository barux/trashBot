source ~/miniconda3/etc/profile.d/conda.sh

source .env

conda activate trashbot

pm2 start trash_bot.py --name trashbot --interpreter python -f
