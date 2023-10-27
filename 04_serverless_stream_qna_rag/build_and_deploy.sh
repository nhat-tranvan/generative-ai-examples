#!/bin/bash
current_root=$(pwd)
echo Working place: $current_root

# 01. install required tools & dependencies
# npm install -g aws-cdk

# 02. build lambda functions
py_functions=('functions/document_indexer' 'functions/layers/python/core')
for str in ${py_functions[@]}; do
    echo Building $str
    TARGET_FILE="$current_root/$str/requirements.txt"
    if test -f $TARGET_FILE; then
        echo Target $current_root/$str
        cd $str
        pip3 install -r requirements.txt --target $current_root/$str
    else
        echo "$TARGET_FILE does not exist."
    fi
    cd $current_root
done

node_functions=('functions/document_qna_stream')
for str in ${node_functions[@]}; do
    echo $str
    cd $str
    npm install
    cd $current_root
done

# 03. cdk build & deploy
pip install -r requirements.txt
# cdk deploy
