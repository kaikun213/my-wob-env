#!/bin/bash
# sync demo data from S3

export AWS_ACCESS_KEY_ID="AKIAJ7V4FOJ3FRK7QFTA"
export AWS_SECRET_ACCESS_KEY="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"

ENV_ID=$1
DEMO_PATH=$2

aws s3 sync s3://openai-vnc-wob-demonstrations-dev/$ENV_ID $DEMO_PATH/$ENV_ID
