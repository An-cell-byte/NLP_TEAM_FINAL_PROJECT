from baseline.core import read_document,chunk_pages
import pytest

def test_texto_y_fragmentos():
 pages=read_document('ejemplo.txt',b'Un documento de prueba.')
 chunks=chunk_pages('ejemplo.txt',pages)
 assert len(chunks)==1 and chunks[0].page==1

def test_archivo_vacio():
 with pytest.raises(ValueError):read_document('vacio.txt',b'')
