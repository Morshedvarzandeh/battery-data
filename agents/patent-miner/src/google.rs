use crate::model::{
    Citation, Classification, FamilyKey, LocalizedText, Party, PatentRecord, Rights, SourceRef,
};
use crate::RECORD_SCHEMA_VERSION;
use anyhow::{bail, Result};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub const PROVIDER: &str = "google_patents_public_data";
pub const TERMS_URL: &str = "https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data";

pub fn normalize(raw: &Value, taxonomy_version: &str, retrieved_at: &str) -> Result<PatentRecord> {
    let raw_publication = string_field(raw, "publication_number")
        .or_else(|| string_field(raw, "publication_id"))
        .ok_or_else(|| anyhow::anyhow!("Google record has no publication_number"))?;
    let publication_number = normalize_number(&raw_publication);
    if publication_number.len() < 4 {
        bail!("invalid publication_number {raw_publication}");
    }
    let authority = string_field(raw, "country_code")
        .map(|s| normalize_authority(&s))
        .filter(|s| s.len() == 2)
        .unwrap_or_else(|| publication_number[0..2].to_string());
    let kind_code = string_field(raw, "kind_code").map(|s| normalize_token(&s));
    let document_number = publication_number
        .strip_prefix(&authority)
        .unwrap_or(&publication_number)
        .to_string();

    let family_id = string_field(raw, "family_id").unwrap_or_else(|| {
        let mut h = Sha256::new();
        h.update(publication_number.as_bytes());
        format!("artificial:{}", hex::encode(h.finalize()))
    });
    let family_kind = if family_id.starts_with("artificial:") {
        "artificial"
    } else {
        "simple"
    };

    let titles = localized(raw.get("title"));
    let abstracts = localized(raw.get("abstract"));
    let mut classifications = Vec::new();
    classifications.extend(classification_values(raw.get("cpc"), "CPC"));
    classifications.extend(classification_values(raw.get("ipc"), "IPC"));
    classifications.extend(classification_values(raw.get("uspc"), "USPC"));
    classifications.extend(classification_values(raw.get("fi"), "FI"));
    classifications.extend(classification_values(raw.get("fterm"), "F_TERM"));
    classifications.sort_by(|a, b| a.scheme.cmp(&b.scheme).then(a.code.cmp(&b.code)));
    classifications.dedup_by(|a, b| a.scheme == b.scheme && a.code == b.code);

    let mut parties = Vec::new();
    parties.extend(party_values(raw.get("inventor"), "inventor"));
    parties.extend(party_values(raw.get("applicant"), "applicant"));
    parties.extend(party_values(raw.get("assignee"), "assignee"));
    let citations = citation_values(raw.get("citation"));

    let raw_bytes = serde_json::to_vec(raw)?;
    let raw_hash = hex::encode(Sha256::digest(&raw_bytes));
    let source_record_url = format!("https://patents.google.com/patent/{publication_number}");

    Ok(PatentRecord {
        schema_version: RECORD_SCHEMA_VERSION.to_string(),
        taxonomy_version: taxonomy_version.to_string(),
        publication_number: publication_number.clone(),
        authority,
        document_number,
        kind_code,
        application_number: string_field(raw, "application_number").map(|s| normalize_token(&s)),
        pct_number: string_field(raw, "pct_number").map(|s| normalize_token(&s)),
        filing_date: date_field(raw, "filing_date"),
        priority_date: date_field(raw, "priority_date"),
        publication_date: date_field(raw, "publication_date"),
        grant_date: date_field(raw, "grant_date"),
        withdrawn: bool_field(raw, "withdrawn"),
        family_keys: vec![FamilyKey {
            kind: family_kind.to_string(),
            provider: PROVIDER.to_string(),
            id: family_id,
        }],
        titles,
        abstracts,
        // Full claims are deliberately not copied from the upstream record.
        // A later source-specific rights adapter may add hashes/locators.
        claims: Vec::new(),
        classifications,
        parties,
        citations,
        annotations: Vec::new(),
        source: SourceRef {
            provider: PROVIDER.to_string(),
            record_id: raw_publication,
            record_url: Some(source_record_url),
            retrieved_at: retrieved_at.to_string(),
            source_updated_at: None,
            record_sha256: raw_hash,
        },
        rights: Rights {
            metadata_license: "source-controlled; verify terms snapshot".to_string(),
            metadata_terms_url: Some(TERMS_URL.to_string()),
            fulltext_redistributable: false,
            fulltext_license: None,
            fulltext_terms_url: Some(TERMS_URL.to_string()),
        },
    })
}

fn string_field(value: &Value, key: &str) -> Option<String> {
    scalar_string(value.get(key)?)
}

fn scalar_string(value: &Value) -> Option<String> {
    match value {
        Value::String(s) if !s.trim().is_empty() => Some(s.trim().to_string()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

fn bool_field(value: &Value, key: &str) -> Option<bool> {
    match value.get(key)? {
        Value::Bool(v) => Some(*v),
        Value::Number(v) => v.as_i64().map(|n| n != 0),
        Value::String(v) => match v.to_lowercase().as_str() {
            "true" | "1" => Some(true),
            "false" | "0" => Some(false),
            _ => None,
        },
        _ => None,
    }
}

fn date_field(value: &Value, key: &str) -> Option<String> {
    let raw = string_field(value, key)?;
    let digits: String = raw.chars().filter(char::is_ascii_digit).collect();
    if digits.len() != 8 || digits == "00000000" {
        return None;
    }
    Some(format!("{}-{}-{}", &digits[0..4], &digits[4..6], &digits[6..8]))
}

fn localized(value: Option<&Value>) -> Vec<LocalizedText> {
    let mut out = Vec::new();
    match value {
        Some(Value::Array(items)) => {
            for item in items {
                if let Some(text) = item.get("text").and_then(scalar_string) {
                    let language = item
                        .get("language")
                        .and_then(scalar_string)
                        .unwrap_or_else(|| "und".to_string());
                    out.push(LocalizedText {
                        language: language.to_lowercase(),
                        text,
                        machine_translation: false,
                    });
                } else if let Some(text) = scalar_string(item) {
                    out.push(LocalizedText {
                        language: "und".to_string(),
                        text,
                        machine_translation: false,
                    });
                }
            }
        }
        Some(item) => {
            if let Some(text) = scalar_string(item) {
                out.push(LocalizedText {
                    language: "und".to_string(),
                    text,
                    machine_translation: false,
                });
            }
        }
        None => {}
    }
    out
}

fn classification_values(value: Option<&Value>, scheme: &str) -> Vec<Classification> {
    let mut out = Vec::new();
    let Some(value) = value else { return out };
    let items: Vec<&Value> = match value {
        Value::Array(v) => v.iter().collect(),
        other => vec![other],
    };
    for item in items {
        let code = item
            .get("code")
            .and_then(scalar_string)
            .or_else(|| scalar_string(item));
        if let Some(code) = code {
            out.push(Classification {
                scheme: scheme.to_string(),
                code: code.trim().to_uppercase(),
                version: item.get("version").and_then(scalar_string),
                inventive: item.get("inventive").and_then(Value::as_bool),
                first_position: item
                    .get("first")
                    .or_else(|| item.get("first_position"))
                    .and_then(Value::as_bool),
            });
        }
    }
    out
}

fn party_values(value: Option<&Value>, role: &str) -> Vec<Party> {
    let Some(value) = value else { return Vec::new() };
    let items: Vec<&Value> = match value {
        Value::Array(v) => v.iter().collect(),
        other => vec![other],
    };
    items
        .into_iter()
        .enumerate()
        .filter_map(|(idx, item)| {
            let name = item
                .get("name")
                .and_then(scalar_string)
                .or_else(|| scalar_string(item))?;
            Some(Party {
                role: role.to_string(),
                name,
                country: item.get("country_code").and_then(scalar_string),
                sequence: Some((idx + 1) as u32),
            })
        })
        .collect()
}

fn citation_values(value: Option<&Value>) -> Vec<Citation> {
    let Some(value) = value else { return Vec::new() };
    let items: Vec<&Value> = match value {
        Value::Array(v) => v.iter().collect(),
        other => vec![other],
    };
    items
        .into_iter()
        .filter_map(|item| {
            let number = item
                .get("publication_number")
                .or_else(|| item.get("publication_id"))
                .and_then(scalar_string)
                .or_else(|| scalar_string(item))?;
            Some(Citation {
                publication_number: normalize_number(&number),
                category: item.get("category").and_then(scalar_string),
                cited_by: item.get("type").and_then(scalar_string),
            })
        })
        .collect()
}

fn normalize_authority(value: &str) -> String {
    value
        .chars()
        .filter(char::is_ascii_alphabetic)
        .take(2)
        .flat_map(char::to_uppercase)
        .collect()
}

fn normalize_token(value: &str) -> String {
    value
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || "/.-".contains(*c))
        .flat_map(char::to_uppercase)
        .collect()
}

pub fn normalize_number(value: &str) -> String {
    value
        .chars()
        .filter(char::is_ascii_alphanumeric)
        .flat_map(char::to_uppercase)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn normalizes_google_nested_record_without_copying_claims() {
        let raw = json!({
            "publication_number": "US-2024-0123456-A1",
            "country_code": "US",
            "kind_code": "A1",
            "family_id": 999,
            "publication_date": 20240314,
            "title": [{"language":"en", "text":"Lithium-ion battery cooling"}],
            "abstract": [{"language":"en", "text":"A battery thermal management system."}],
            "claims": [{"text":"claim body deliberately not copied"}],
            "cpc": [{"code":"H01M 10/613", "inventive":true}],
            "assignee": [{"name":"Example Corp", "country_code":"US"}]
        });
        let result = normalize(&raw, "1.0.0", "2026-08-24T00:00:00Z").unwrap();
        assert_eq!(result.publication_number, "US20240123456A1");
        assert_eq!(result.publication_date.as_deref(), Some("2024-03-14"));
        assert_eq!(result.classifications[0].scheme, "CPC");
        assert!(result.claims.is_empty());
        assert!(!result.rights.fulltext_redistributable);
    }
}
