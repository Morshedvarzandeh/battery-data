use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LocalizedText {
    pub language: String,
    pub text: String,
    #[serde(default)]
    pub machine_translation: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FamilyKey {
    pub kind: String,
    pub provider: String,
    pub id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Classification {
    pub scheme: String,
    pub code: String,
    #[serde(default)]
    pub version: Option<String>,
    #[serde(default)]
    pub inventive: Option<bool>,
    #[serde(default)]
    pub first_position: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Party {
    pub role: String,
    pub name: String,
    #[serde(default)]
    pub country: Option<String>,
    #[serde(default)]
    pub sequence: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Citation {
    pub publication_number: String,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default)]
    pub cited_by: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Locator {
    pub kind: String,
    #[serde(default)]
    pub page: Option<u32>,
    #[serde(default)]
    pub section: Option<String>,
    #[serde(default)]
    pub quote: Option<String>,
    #[serde(default)]
    pub field_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claim {
    pub number: u32,
    pub language: String,
    #[serde(default)]
    pub text: Option<String>,
    pub text_sha256: String,
    #[serde(default)]
    pub independent: Option<bool>,
    #[serde(default)]
    pub depends_on: Vec<u32>,
    pub redistributable: bool,
    #[serde(default)]
    pub locator: Option<Locator>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Annotation {
    pub taxon_id: String,
    pub method: String,
    pub score: f64,
    #[serde(default)]
    pub rule_id: Option<String>,
    pub evidence: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceRef {
    pub provider: String,
    pub record_id: String,
    #[serde(default)]
    pub record_url: Option<String>,
    pub retrieved_at: String,
    #[serde(default)]
    pub source_updated_at: Option<String>,
    pub record_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rights {
    pub metadata_license: String,
    #[serde(default)]
    pub metadata_terms_url: Option<String>,
    pub fulltext_redistributable: bool,
    #[serde(default)]
    pub fulltext_license: Option<String>,
    #[serde(default)]
    pub fulltext_terms_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatentRecord {
    pub schema_version: String,
    pub taxonomy_version: String,
    pub publication_number: String,
    pub authority: String,
    pub document_number: String,
    #[serde(default)]
    pub kind_code: Option<String>,
    #[serde(default)]
    pub application_number: Option<String>,
    #[serde(default)]
    pub pct_number: Option<String>,
    #[serde(default)]
    pub filing_date: Option<String>,
    #[serde(default)]
    pub priority_date: Option<String>,
    #[serde(default)]
    pub publication_date: Option<String>,
    #[serde(default)]
    pub grant_date: Option<String>,
    #[serde(default)]
    pub withdrawn: Option<bool>,
    pub family_keys: Vec<FamilyKey>,
    #[serde(default)]
    pub titles: Vec<LocalizedText>,
    #[serde(default)]
    pub abstracts: Vec<LocalizedText>,
    #[serde(default)]
    pub claims: Vec<Claim>,
    #[serde(default)]
    pub classifications: Vec<Classification>,
    #[serde(default)]
    pub parties: Vec<Party>,
    #[serde(default)]
    pub citations: Vec<Citation>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub annotations: Vec<Annotation>,
    pub source: SourceRef,
    pub rights: Rights,
}

impl PatentRecord {
    pub fn searchable_text(&self) -> String {
        let mut out = String::new();
        for item in self.titles.iter().chain(self.abstracts.iter()) {
            out.push_str(&item.text);
            out.push('\n');
        }
        for claim in &self.claims {
            if let Some(text) = &claim.text {
                out.push_str(text);
                out.push('\n');
            }
        }
        out.to_lowercase()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationResult {
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

impl ValidationResult {
    pub fn valid(&self) -> bool {
        self.errors.is_empty()
    }
}
