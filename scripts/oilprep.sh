#!/bin/bash
# Gather and craft what the oil chain needs: 1 refinery, 3 chemical plants, pipes. Bricks come from the stone furnace at -92,-24.
cd "$(dirname "$0")/.."
s(){ ./step.sh "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(str(d.get('observation',d))[:170])"; }
W=.venv/bin/python; 
$W scripts/withdraw.py steel-plate 80; $W scripts/withdraw.py stone 60; $W scripts/withdraw.py iron-plate 250; $W scripts/withdraw.py copper-plate 120
s '{"skill":"goto","params":{"position":"-91,-22"}}'
s '{"skill":"feed","params":{"item_prototype":"Coal","target_prototype":"StoneFurnace","target_position":"-92,-24","quantity":8}}'
s '{"skill":"feed","params":{"item_prototype":"Stone","target_prototype":"StoneFurnace","target_position":"-92,-24","quantity":40}}'
sleep 25
s '{"skill":"collect","params":{"item_prototype":"StoneBrick","source_position":"-92,-24","quantity":20}}'
s '{"skill":"craft","params":{"item_prototype":"OilRefinery","count":1}}'
s '{"skill":"craft","params":{"item_prototype":"ChemicalPlant","count":3}}'
s '{"skill":"craft","params":{"item_prototype":"Pipe","count":40}}'
s '{"skill":"inspect","params":{}}'
