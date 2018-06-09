#!/usr/bin/env bash
# Usage: upload_directory.sh demonstrator_id directory
# Expects an env_id as an environment variable
# Example: env_id='flashgames.DuskDrive-v0' upload_directory.sh demonstrator_EjQjtJoZsLG8dzal /tmp/demo/1475625047-x43pk5scrzsupf-0/

set -eu


if [ "$#" -ne 3 ]; then
    echo "Takes three arguments:"
	echo "    src_path (e.g. /tmp/demo/realwob/db/delta)"
	echo "    dest_path (e.g. db/)"
	echo "    s3-bucket (e.g. openai-vnc-realwob-dev)"
    echo "Usage example: ./upload_directory.sh db /tmp/demo/realwob/db/delta"
    exit 1
fi

# Argument names
curr_path=$( pwd )
src_path=$1
dest_path=$2
bucket=$3

if ! [ -d "$src_path" ]; then
	echo "Error: $src_path is not a directory"
	exit 1
fi

echo "Examining $src_path"

# Configure AWS with our user: anonymous-public-universe-uploader
export AWS_ACCESS_KEY_ID="AKIAJ7V4FOJ3FRK7QFTA"
export AWS_SECRET_ACCESS_KEY="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"

echo "Gzipping directory: $src_path. This may take a while..."

cd `dirname $src_path`  # move to the parent
tarball="$(basename $src_path).tar.gz"
tar -zcvf $tarball $(basename $src_path)

# Copy the gzipped dir to S3
echo "Uploading: aws s3 cp $tarball s3://$bucket/$dest_path/$tarball"

$curr_path/bin/upload.py $tarball $bucket $dest_path/$tarball
# aws s3 cp $tarball $s3_dest

# Move out of the way so we don't re-upload later
mkdir -p /tmp/uploaded-demos
mv $tarball /tmp/uploaded-demos/

# Don't need the original anymore
rm -rf $src_path

echo "Done uploading"
