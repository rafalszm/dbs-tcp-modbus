import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const repoRoot = process.cwd();
const outputPath = path.join(repoRoot, "docs", "dbs_tcp_modbus_mapping_template.xlsx");
const previewPath = path.join(repoRoot, "docs", "dbs_tcp_modbus_mapping_template_preview.png");

const columns = [
  ["key", "Wymagane. Stabilny identyfikator encji, bez polskich znakow i spacji."],
  ["name", "Wymagane. Nazwa encji widoczna w Home Assistant."],
  ["function", "Wymagane. Kod funkcji Modbus: 1, 2, 3 albo 4."],
  ["address", "Wymagane. Adres zero-based, zgodny z pymodbus."],
  ["type", "Wymagane. coil, discrete, bit, uint16, int16, uint32, int32 albo float32."],
  ["bit", "Tylko dla type=bit. Zakres 0-15, bit 0 to najmniej znaczacy bit rejestru."],
  ["unit", "Opcjonalnie. Jednostka, np. bar, m3/h, kWh."],
  ["scale", "Opcjonalnie. Mnoznik wartosci. Puste pole oznacza 1."],
  ["offset", "Opcjonalnie. Przesuniecie wartosci. Puste pole oznacza 0."],
  ["precision", "Opcjonalnie. Liczba miejsc po przecinku."],
  ["device_class", "Opcjonalnie. Klasa HA, np. pressure, power, energy, voltage."],
  ["state_class", "Opcjonalnie. measurement, total albo total_increasing."],
  ["icon", "Opcjonalnie. Ikona HA, np. mdi:pump."],
  ["section", "Opcjonalnie. Grupa lub blok technologiczny."],
  ["enabled_by_default", "Opcjonalnie. true/false. Uzyj false dla rezerw i Static_*."],
  ["count", "Opcjonalnie. Liczba rejestrow/bitow do odczytu, zwykle puste."],
  ["word_order", "Opcjonalnie dla 32-bit. high_low albo low_high."],
  ["byte_order", "Opcjonalnie. big albo little."],
];

const examples = [
  [
    "station_pressure",
    "Cisnienie",
    3,
    100,
    "uint16",
    "",
    "bar",
    0.1,
    0,
    1,
    "pressure",
    "measurement",
    "",
    "Hydrofornia",
    "true",
    "",
    "",
    "",
  ],
  [
    "pump_running",
    "Pompa pracuje",
    3,
    10,
    "bit",
    3,
    "",
    1,
    0,
    "",
    "running",
    "",
    "",
    "IO_10",
    "true",
    "",
    "",
    "",
  ],
  [
    "flow_raw",
    "Przeplyw surowa",
    3,
    34,
    "float32",
    "",
    "m3/h",
    1,
    0,
    3,
    "",
    "measurement",
    "mdi:waves-arrow-right",
    "Pomiary",
    "true",
    "",
    "high_low",
    "big",
  ],
  [
    "counter_raw",
    "Licznik surowa",
    3,
    52,
    "uint32",
    "",
    "m3",
    1,
    0,
    0,
    "",
    "total_increasing",
    "mdi:counter",
    "Liczniki",
    "true",
    "",
    "high_low",
    "big",
  ],
  [
    "static_reserve",
    "Static reserve",
    3,
    200,
    "uint16",
    "",
    "",
    1,
    0,
    "",
    "",
    "",
    "",
    "Rezerwa",
    "false",
    "",
    "",
    "",
  ],
];

const dictionaries = [
  ["Pole", "Dozwolone wartosci"],
  ["function", "1,2,3,4"],
  ["type", "coil,discrete,bit,uint16,int16,uint32,int32,float32"],
  ["enabled_by_default", "true,false"],
  ["word_order", "high_low,low_high"],
  ["byte_order", "big,little"],
  ["state_class", "measurement,total,total_increasing"],
  ["bit", "0-15"],
];

const instructions = [
  ["DBS TCP Modbus - szablon mapy rejestrow"],
  [""],
  ["Wypelnij arkusz 'Mapa CSV'. Pierwszy wiersz zawiera dokladne naglowki wymagane przez integracje."],
  ["Do Home Assistant wklej eksport CSV z arkusza 'Mapa CSV', razem z wierszem naglowka."],
  ["Adresy sa zero-based, tak jak w pymodbus i w ustaleniach z automatykiem."],
  ["Dla pojedynczych bitow w rejestrach 03/04 ustaw type=bit oraz bit=0..15."],
  ["Dla Float/UDInt/DInt uzywaj adresu pierwszego slowa. Gdy wartosci sa bledne, sprawdz word_order high_low/low_high."],
  ["Rezerwy i Static_* najlepiej ustawic enabled_by_default=false."],
  [""],
  ["Minimalne wymagane kolumny", "key,name,function,address,type"],
  ["Wersja integracji wymagana dla type=bit", "v1.0.4 albo nowsza"],
];

const workbook = Workbook.create();
const map = workbook.worksheets.add("Mapa CSV");
const guide = workbook.worksheets.add("Instrukcja");
const dict = workbook.worksheets.add("Slowniki");

map.showGridLines = false;
guide.showGridLines = false;
dict.showGridLines = false;
map.tabColor = "#1F4E78";
guide.tabColor = "#5B9BD5";
dict.tabColor = "#A6A6A6";

const header = columns.map(([name]) => name);
map.getRange("A1:R1").values = [header];
map.getRange("A2:R6").values = examples;
map.getRange("A7:R206").values = Array.from({ length: 200 }, () => Array(18).fill(""));

map.getRange("A1:R1").format = {
  fill: "#1F4E78",
  font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 },
};
map.getRange("A2:R206").format.font = { name: "Arial", size: 10 };
map.getRange("A1:R206").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
map.getRange("A2:R206").format.verticalAlignment = "center";
map.getRange("A2:B206").format.numberFormat = "@";
map.getRange("C2:D206").format.numberFormat = "0";
map.getRange("F2:F206").format.numberFormat = "0";
map.getRange("H2:I206").format.numberFormat = "0.############";
map.getRange("J2:J206").format.numberFormat = "0";
map.freezePanes.freezeRows(1);

const widths = [26, 28, 10, 10, 13, 8, 12, 10, 10, 11, 16, 18, 18, 18, 18, 9, 13, 12];
for (let i = 0; i < widths.length; i += 1) {
  map.getRangeByIndexes(0, i, 206, 1).format.columnWidth = widths[i];
}

map.tables.add("A1:R206", true, "DBSModbusMap");
map.dataValidations.add({ range: "C2:C206", rule: { type: "list", values: ["1", "2", "3", "4"] } });
map.dataValidations.add({
  range: "E2:E206",
  rule: { type: "list", values: ["coil", "discrete", "bit", "uint16", "int16", "uint32", "int32", "float32"] },
});
map.dataValidations.add({ range: "F2:F206", rule: { type: "whole", operator: "between", formula1: 0, formula2: 15 } });
map.dataValidations.add({ range: "O2:O206", rule: { type: "list", values: ["true", "false"] } });
map.dataValidations.add({ range: "Q2:Q206", rule: { type: "list", values: ["high_low", "low_high"] } });
map.dataValidations.add({ range: "R2:R206", rule: { type: "list", values: ["big", "little"] } });

map.getRange("A2:R6").format.fill = "#EAF2F8";
map.getRange("A7:R206").format.fill = "#FFFFFF";

guide.getRange("A1:B11").values = instructions;
guide.getRange("A1:B1").format = {
  font: { name: "Arial", bold: true, size: 14, color: "#1F1F1F" },
};
guide.getRange("A3:B11").format.font = { name: "Arial", size: 10 };
guide.getRange("A10:B11").format = {
  fill: "#EAF2F8",
  font: { name: "Arial", size: 10 },
  borders: { preset: "all", style: "thin", color: "#D9E2F3" },
};
guide.getRange("A:A").format.columnWidth = 72;
guide.getRange("B:B").format.columnWidth = 32;

const glossary = [["Kolumna", "Opis"], ...columns];
dict.getRangeByIndexes(0, 0, glossary.length, 2).values = glossary;
dict.getRangeByIndexes(0, 3, dictionaries.length, 2).values = dictionaries;
dict.getRange("A1:B1").format = {
  fill: "#1F4E78",
  font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 },
};
dict.getRange("D1:E1").format = {
  fill: "#1F4E78",
  font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 },
};
dict.getRangeByIndexes(0, 0, glossary.length, 2).format.borders = {
  preset: "all",
  style: "thin",
  color: "#D9E2F3",
};
dict.getRangeByIndexes(0, 3, dictionaries.length, 2).format.borders = {
  preset: "all",
  style: "thin",
  color: "#D9E2F3",
};
dict.getRange("A:E").format.font = { name: "Arial", size: 10 };
dict.getRange("A:A").format.columnWidth = 24;
dict.getRange("B:B").format.columnWidth = 86;
dict.getRange("D:D").format.columnWidth = 24;
dict.getRange("E:E").format.columnWidth = 48;

workbook.recalculate();

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const preview = await workbook.render({
  sheetName: "Mapa CSV",
  range: "A1:R12",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(outputPath);
console.log(previewPath);
