//! Vision API クライアント

use super::auth::{find_credentials, get_access_token, ServiceAccountCredentials};
use anyhow::{Context, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::RwLock;

const VISION_API_URL: &str = "https://vision.googleapis.com/v1/images:annotate";

/// Vision APIクライアント
pub struct VisionClient {
    credentials: ServiceAccountCredentials,
    access_token: Arc<RwLock<Option<String>>>,
    http_client: reqwest::Client,
}

impl VisionClient {
    /// 新しいクライアントを作成
    pub fn new() -> Result<Self> {
        let credentials = find_credentials()?;
        Ok(Self {
            credentials,
            access_token: Arc::new(RwLock::new(None)),
            http_client: reqwest::Client::new(),
        })
    }
    
    /// アクセストークンを取得（キャッシュあり）
    async fn get_token(&self) -> Result<String> {
        // キャッシュされたトークンがあれば使用
        {
            let token = self.access_token.read().await;
            if let Some(ref t) = *token {
                return Ok(t.clone());
            }
        }
        
        // 新しいトークンを取得
        let new_token = get_access_token(&self.credentials).await?;
        
        // キャッシュに保存
        {
            let mut token = self.access_token.write().await;
            *token = Some(new_token.clone());
        }
        
        Ok(new_token)
    }
    
    /// 画像からテキストを抽出
    pub async fn extract_text(&self, image_path: impl AsRef<Path>) -> Result<String> {
        let image_data = std::fs::read(image_path.as_ref())
            .with_context(|| format!("画像ファイルの読み込みに失敗: {:?}", image_path.as_ref()))?;
        
        let base64_image = STANDARD.encode(&image_data);
        
        let request = VisionRequest {
            requests: vec![AnnotateImageRequest {
                image: Image {
                    content: base64_image,
                },
                features: vec![Feature {
                    feature_type: "DOCUMENT_TEXT_DETECTION".to_string(),
                    max_results: 1,
                }],
                image_context: Some(ImageContext {
                    language_hints: vec!["ja".to_string(), "en".to_string()],
                }),
            }],
        };
        
        let token = self.get_token().await?;
        
        let response = self.http_client
            .post(VISION_API_URL)
            .bearer_auth(&token)
            .json(&request)
            .send()
            .await
            .context("Vision APIリクエストに失敗")?;
        
        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            anyhow::bail!("Vision API エラー: {}", error_text);
        }
        
        let vision_response: VisionResponse = response
            .json()
            .await
            .context("Vision APIレスポンスのパースに失敗")?;
        
        // テキストを抽出
        let text = vision_response
            .responses
            .first()
            .and_then(|r| r.full_text_annotation.as_ref())
            .map(|a| a.text.clone())
            .unwrap_or_default();
        
        Ok(text)
    }
}

// Vision API リクエスト/レスポンス構造体

#[derive(Serialize)]
struct VisionRequest {
    requests: Vec<AnnotateImageRequest>,
}

#[derive(Serialize)]
struct AnnotateImageRequest {
    image: Image,
    features: Vec<Feature>,
    #[serde(skip_serializing_if = "Option::is_none")]
    image_context: Option<ImageContext>,
}

#[derive(Serialize)]
struct Image {
    content: String,
}

#[derive(Serialize)]
struct Feature {
    #[serde(rename = "type")]
    feature_type: String,
    #[serde(rename = "maxResults")]
    max_results: i32,
}

#[derive(Serialize)]
struct ImageContext {
    #[serde(rename = "languageHints")]
    language_hints: Vec<String>,
}

#[derive(Deserialize)]
struct VisionResponse {
    responses: Vec<AnnotateImageResponse>,
}

#[derive(Deserialize)]
struct AnnotateImageResponse {
    #[serde(rename = "fullTextAnnotation")]
    full_text_annotation: Option<TextAnnotation>,
}

#[derive(Deserialize)]
struct TextAnnotation {
    text: String,
}
