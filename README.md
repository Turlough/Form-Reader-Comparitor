# Form reader comparitor
App that takes a "ground-truth" batch of indexed scanned forms, and runs multiple form reading techniques against the batch.
Results are compared and ranked.

All results are saved for later comparison.

Running glm-ocr on ollama locally proved surprisingly accurate and fast, so vision-capable llms are in the mix. But also Tesseract, paddleOCR, EasyOCR, Surya OCR, DocTR, Kraken, etc.

This suggests a strategy pattern or interface/protocol/adapter for OCR methods.

Batches are categorised as Handwritten, Handwritten difficult, Typed, and barcode, etc.

The subset of readers used in any run is configurable. Results for each run are recorded, for each reader.

Separately from evaluation code, natural language is used to query the results database. This app is web based and can choose a separate LLM for analysis.

## Stage 2
Batches are presented as a comma separated text file, EXPORT.TXT that provides a ground-truth index of expected values.

EXPORT.TXT does not have column headings. Col[0] on each row is always the relative path to the image.

The image may be a multipage TIFF or PDF, but only the first page is read.

The natural language results query is limited to one appropriate model that can handle statistical queries well.

### Stage 2 objectives
- Create a desktop python app (PyQt6) that allows the user to:
    - Import EXPORT.TXT
    - Select a subset of OCR techniques.
    - Create 'run' of the batch and record the results of each technique, as well as the imported ground-truth data from EXPORT.TXT, as well as an accuracy estimate
    - Levenshtein Distance is the accuracy metric, measured across all fields (columns) of each result comparison with ground-truth.
    - Time taken for each OCR type is recorded twice- once for concurrent reading, the other for sequential reading.
- Create a web app with an LLM that accepts natural language queries on the resultant database.

## OCR vs LLM
LLMs can query content, e.g. "What is the surname, forename, and DOB of this person". Some LLMs can use text comprehension to locate field data, without prescribing the zone in which the text is found.

With 'pure' OCR methods (e.g. Tesseract), it is necessary to define the rectangle in which the corresponding text is found before reading the text within it.

This means that a separate UI must be used to define the rectangles when 'pure' OCR methods are used. Optionally, it can also be used with LLMs.

It is possible and frequent that only LLMs are in the chosen methods. Therefore, zoning of fields is a secondary concern.





