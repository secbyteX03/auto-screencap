use anyhow::{Context, Result};
use image::imageops::blur;
use serde::{Deserialize, Serialize};
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Debug, Deserialize)]
struct ProcessRequest {
    /// Path to the input image
    path: String,
    /// Optional: Sigma value for gaussian blur (disabled if None)
    blur_sigma: Option<f32>,
    /// Optional: Target dimensions as (width, height)
    resize: Option<(u32, u32)>,
    /// Optional: Output path (defaults to input path + "_processed")
    out_path: Option<String>,
}

#[derive(Debug, Serialize)]
struct ProcessResponse {
    ok: bool,
    out_path: String,
    msg: String,
}

fn process_image(request: &ProcessRequest) -> Result<ProcessResponse> {
    // Determine output path
    let in_path = PathBuf::from(&request.path);
    let out_path = match &request.out_path {
        Some(p) => PathBuf::from(p),
        None => {
            let mut p = in_path.clone();
            let stem = p.file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("screenshot");
            let ext = p.extension()
                .and_then(|s| s.to_str())
                .unwrap_or("png");
            p.set_file_name(format!("{}_processed.{}", stem, ext));
            p
        }
    };

    // Load the image
    let mut img = image::open(&in_path)
        .with_context(|| format!("Failed to open image: {}", in_path.display()))?;

    // Apply transformations
    if let Some((width, height)) = request.resize {
        img = img.resize_exact(
            width,
            height,
            image::imageops::FilterType::Lanczos3,
        );
    }

    if let Some(sigma) = request.blur_sigma {
        if sigma > 0.0 {
            img = blur(&img, sigma);
        }
    }

    // Save the result
    img.save(&out_path)
        .with_context(|| format!("Failed to save image: {}", out_path.display()))?;

    Ok(ProcessResponse {
        ok: true,
        out_path: out_path.to_string_lossy().into_owned(),
        msg: "Image processed successfully".to_string(),
    })
}

fn main() {
    // Simple logger setup
    simple_logger::SimpleLogger::new()
        .with_level(log::LevelFilter::Warn)
        .env()
        .init()
        .ok();

    // Read JSON from stdin
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        let response = ProcessResponse {
            ok: false,
            out_path: String::new(),
            msg: format!("Failed to read stdin: {}", e),
        };
        println!("{}", serde_json::to_string(&response).unwrap());
        std::process::exit(1);
    }

    // Parse request
    let request: ProcessRequest = match serde_json::from_str(&input) {
        Ok(r) => r,
        Err(e) => {
            let response = ProcessResponse {
                ok: false,
                out_path: String::new(),
                msg: format!("Invalid request: {}", e),
            };
            println!("{}", serde_json::to_string(&response).unwrap());
            std::process::exit(1);
        }
    };

    // Process the image
    match process_image(&request) {
        Ok(response) => {
            println!("{}", serde_json::to_string(&response).unwrap());
            std::process::exit(0);
        }
        Err(e) => {
            let response = ProcessResponse {
                ok: false,
                out_path: String::new(),
                msg: format!("Processing failed: {}", e),
            };
            println!("{}", serde_json::to_string(&response).unwrap());
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::tempdir;

    #[test]
    fn test_process_image() -> Result<()> {
        // Create a temporary directory
        let dir = tempdir()?;
        let input_path = dir.path().join("test.png");
        
        // Create a small test image (1x1 pixel)
        let img = image::RgbaImage::new(1, 1);
        img.save(&input_path)?;

        // Test request
        let request = ProcessRequest {
            path: input_path.to_string_lossy().into_owned(),
            blur_sigma: Some(1.0),
            resize: Some((2, 2)),
            out_path: None,
        };

        // Process the image
        let response = process_image(&request)?;
        
        // Verify the output
        assert!(response.ok);
        assert!(PathBuf::from(&response.out_path).exists());
        
        Ok(())
    }
}
