use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::collections::HashSet;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct Taxonomy {
    pub taxonomy_version: String,
    pub coverage_contract: CoverageContract,
    pub taxa: Vec<Taxon>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CoverageContract {
    pub primary_prefixes: Vec<String>,
    #[serde(default)]
    pub historical_prefixes: Vec<String>,
    #[serde(default)]
    pub cross_domain_profiles: Vec<CrossDomainProfile>,
    #[serde(default)]
    pub exclusion_profiles: Vec<ExclusionProfile>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CrossDomainProfile {
    pub id: String,
    pub classification_prefixes: Vec<String>,
    pub required_terms: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExclusionProfile {
    pub id: String,
    pub classification_prefixes: Vec<String>,
    pub unless_terms: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Taxon {
    pub id: String,
    pub facet: String,
    pub code: String,
    pub label: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub parent: Option<String>,
    pub rules: Rules,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Rules {
    #[serde(default)]
    pub classification_prefixes: Vec<String>,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub negative_keywords: Vec<String>,
}

impl Taxonomy {
    pub fn load(path: &Path) -> Result<Self> {
        let bytes = fs::read(path)
            .with_context(|| format!("cannot read taxonomy {}", path.display()))?;
        let taxonomy: Self = serde_json::from_slice(&bytes)
            .with_context(|| format!("invalid taxonomy JSON {}", path.display()))?;
        taxonomy.validate()?;
        Ok(taxonomy)
    }

    pub fn validate(&self) -> Result<()> {
        if self.taxonomy_version.trim().is_empty() {
            bail!("taxonomy_version is empty");
        }
        if self.coverage_contract.primary_prefixes.is_empty() {
            bail!("coverage_contract.primary_prefixes is empty");
        }
        let mut ids = HashSet::new();
        for taxon in &self.taxa {
            if taxon.id != format!("{}/{}", taxon.facet, taxon.code) {
                bail!(
                    "taxon {} must equal facet/code ({}/{})",
                    taxon.id,
                    taxon.facet,
                    taxon.code
                );
            }
            if !ids.insert(taxon.id.as_str()) {
                bail!("duplicate taxon id {}", taxon.id);
            }
            if taxon.rules.classification_prefixes.is_empty()
                && taxon.rules.keywords.is_empty()
            {
                bail!("taxon {} has no classification or keyword rule", taxon.id);
            }
        }
        for taxon in &self.taxa {
            if let Some(parent) = &taxon.parent {
                if !ids.contains(parent.as_str()) {
                    bail!("taxon {} has unknown parent {}", taxon.id, parent);
                }
            }
        }
        Ok(())
    }
}

pub fn normalize_classification(code: &str) -> String {
    code.chars()
        .filter(|c| !c.is_whitespace() && *c != '-' && *c != '.')
        .flat_map(char::to_uppercase)
        .collect()
}

pub fn code_has_prefix(code: &str, prefix: &str) -> bool {
    normalize_classification(code).starts_with(&normalize_classification(prefix))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classification_normalization_preserves_hierarchy() {
        assert_eq!(normalize_classification("H01M 10/0525"), "H01M10/0525");
        assert!(code_has_prefix("H01M 10/0525", "H01M10/052"));
    }
}
