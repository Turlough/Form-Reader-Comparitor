### Index (or Field)
An attribute of a document or form, such as "Forename", "Surname", "Date of Birth", etc.

### Project
A collection of batches (see Batch) that must processed in the same way.
A project will have a consistent set of Index fields that are read from all documents within the project.
A project always organised into batches, which are smaller groupings of documents- the smaller groups makes processing easier to manage.

### Batch
A batch is a folder containing a set of scanned documents, presented as TIF or PDF images.
All documents within a batch belong to the same project, i.e. they have a common set of indexes.
A batch will have an Index file defining the values of these indexes for each document in the batch.

### Index File
An index file is text file containing a path to an image or PDF and index values.

### EXPORT.TXT
This is a common format. It is named like this because it is exported and named automatically by a third-party scanning/indexing app.
The file is normally comma separated, and does not contain headers. The first column is normally the path to the image.

### Ground Truth
The imported index file represents the ground truth for each index value. Values read by LLM may differ from this.


