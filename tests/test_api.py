"""Tests for nucleosize API endpoints."""


def test_existing_dna_entry(client, mock_data):
    """Test that an existing DNA/RNA entry returns correct length."""
    response = client.get("/api/1abc")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "1abc"
    assert data["total_na_length"] == 150


def test_existing_rna_entry(client, mock_data):
    """Test that an existing RNA entry returns correct length."""
    response = client.get("/api/2xyz")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "2xyz"
    assert data["total_na_length"] == 200


def test_existing_non_nucleic_acid_entry(client, mock_data):
    """Test that an existing non-nucleic acid entry returns 0 length."""
    # 4ghi is in valid_pdb_ids but not in nav_lengths
    response = client.get("/api/4ghi")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "4ghi"
    assert data["total_na_length"] == 0


def test_non_existing_entry(client):
    """Test that a non-existing PDB ID returns 404."""
    response = client.get("/api/9999")
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_new_entry_format_pdb_0000xxxx(client, mock_data):
    """Test that new PDB ID format (pdb_0000xxxx) is handled correctly."""
    # pdb_00001abc should be transformed to 1abc
    response = client.get("/api/pdb_00001abc")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "pdb_00001abc"  # Original format preserved in response
    assert data["total_na_length"] == 150


def test_new_entry_format_non_nucleic_acid(client, mock_data):
    """Test new format with non-nucleic acid entry."""
    # pdb_00004ghi should be transformed to 4ghi
    response = client.get("/api/pdb_00004ghi")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "pdb_00004ghi"
    assert data["total_na_length"] == 0


def test_case_insensitive_pdb_id(client, mock_data):
    """Test that PDB ID lookup is case insensitive."""
    response = client.get("/api/1ABC")
    assert response.status_code == 200
    data = response.json()
    assert data["pdbid"] == "1abc"  # Lowercase in response
    assert data["total_na_length"] == 150


def test_health_check_with_data(client):
    """Test health check returns 200 when data is loaded."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "entries" in data
    assert "total_pdb_ids" in data
