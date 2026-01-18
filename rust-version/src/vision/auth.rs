//! Google Cloud 認証処理

use anyhow::{Context, Result};
use jsonwebtoken::{encode, Algorithm, EncodingKey, Header};
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

/// 埋め込み認証情報（ビルド時に埋め込み）
const EMBEDDED_CREDENTIALS: &str = include_str!("../credentials.json");

/// サービスアカウントの認証情報
#[derive(Debug, Deserialize)]
pub struct ServiceAccountCredentials {
    pub client_email: String,
    pub private_key: String,
    pub token_uri: String,
}

/// JWTクレーム
#[derive(Debug, Serialize)]
struct Claims {
    iss: String,
    scope: String,
    aud: String,
    exp: u64,
    iat: u64,
}

/// アクセストークンレスポンス
#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    #[allow(dead_code)]
    expires_in: u64,
    #[allow(dead_code)]
    token_type: String,
}

/// 認証ファイルを取得（埋め込み認証情報を使用）
pub fn find_credentials() -> Result<ServiceAccountCredentials> {
    // 埋め込み認証情報を使用
    serde_json::from_str(EMBEDDED_CREDENTIALS)
        .context("埋め込み認証情報のパースに失敗")
}

/// アクセストークンを取得
pub async fn get_access_token(credentials: &ServiceAccountCredentials) -> Result<String> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let claims = Claims {
        iss: credentials.client_email.clone(),
        scope: "https://www.googleapis.com/auth/cloud-vision".to_string(),
        aud: credentials.token_uri.clone(),
        exp: now + 3600,
        iat: now,
    };
    
    // RSA秘密鍵でJWTを署名
    let key = EncodingKey::from_rsa_pem(credentials.private_key.as_bytes())
        .context("RSA秘密鍵のパースに失敗")?;
    
    let header = Header::new(Algorithm::RS256);
    let jwt = encode(&header, &claims, &key)
        .context("JWTの生成に失敗")?;
    
    // トークンエンドポイントにリクエスト
    let client = reqwest::Client::new();
    let response = client
        .post(&credentials.token_uri)
        .form(&[
            ("grant_type", "urn:ietf:params:oauth:grant-type:jwt-bearer"),
            ("assertion", &jwt),
        ])
        .send()
        .await
        .context("トークンリクエストに失敗")?;
    
    let token_response: TokenResponse = response
        .json()
        .await
        .context("トークンレスポンスのパースに失敗")?;
    
    Ok(token_response.access_token)
}
