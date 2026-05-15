# Stage 1
In this stage we evaluate using one LLM only, glm-ocr, running on ollama.
Refer to the [glossary](GLOSSARY.md) for terminology.
This is PyQt6 app with three horizontal panels and a menu bar

## Panels
Left panel: path to the images
    - Selecting an image path displays the image in the right hand panel
Centre: Table of field values
    - Selecting a cell:
        - Shows the corresponding image in the right hand panel
        - Shows the ground-truth value for the current cell, under the image
Right: Image display, best-fitting the panel and maintaining aspect ratio. 
    - A text area underneath is used for communicating current ground-truth values.
    - Size controls: Autofit, Width, Height
    - Drawing a selection rectangle zooms to selection, and maintains zoom settings for that field until changed. Each field has its own view settings.

## LLMs
Menu item **LLM -> Ollama list**. Clicking the top level **LLM** menu lists the avalailable models from Ollama.
Selecting an item chooses the model.

In this stage:
## Import ground-truth
1. The user may import **EXPORT.TXT** from file system.
    a. Menu Item: **File -> Import**
    b. The table and image lists are populated, and the first image displayed.
    c. Retain last folder selected.
2. When the file is imported, they select menu item **Fields -> Define**. This shows a dialog which allows them to: 
    a. Select the field from list on the left. Initially these are numbered by column number 1, 2, 3, etc- 0 is the image path. This serves as vertical tab strip.
        - If the fields have already be defined, use field names instead of column number
    b.The right hand panel shows two text boxes:
        a. **Field Name**: Friendly name for the field, e.g. Invoice No.
        b. **LLM Prompt**: e.g. "What is the invoice number on this page"
        c. **Active/Inactive** Radio buttons. **Inactive** means this field will not be read by the LLM, so no prompt is required. However, the prompt, if any, is recorded. This enables the user to activate/deactivate the field. If a field is inactive, the corresponding column in the table has a light gray background.
    
    c. Bottom buttons: **Ok, Cancel**. 
            - **Ok** Saves the configuration
            - **Cancel** Close dialog without saving
            
3. Configuration is recorded in **fields.json**, in the same folder as **EXPORT.TXT**.
    - Field name
    - Prompt
    - View Settings: One of: **Auto, width, height, recangle [x, y, w, h]**

## The field table
- Shows the ground-truth values on loading a batch.
- Clicking a cell displays the corresponding image, with that field's view settings applied.
- Cells that are currently being read are highlighted, as soon as the previous field has completed.
- When a cell has been read, the read value is shown in that cell. If it differs from ground truth (i.e. not equal when trimmed), the font color is red.
- If a field is deactivated, the corresponding column in the table has a light gray background.


## Process the imported file
The user selects menu item **Field -> Read Batch**.
The application runs the LLM.
A single thread is used, so this happens sequentially.
1. For each field in a row, the appropriate prompt is from **fields.json** is read and applied.
2. The result is immediately written to the corresponding cell in the table. The next field is highlighted, indicating that it is next to be read.
3. If the read value of any cell is not the same as the ground-truth value, its font is red.
3. This is repeated for each row.






