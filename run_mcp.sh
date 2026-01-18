#!/bin/bash
cd /Users/nimarfranklinmac/Dev/KW_Mem_MCP_Server
export PYTHONPATH="/Users/nimarfranklinmac/Dev/KW_Mem_MCP_Server:$PYTHONPATH"
exec /opt/anaconda3/bin/python -m src.main "$@"
