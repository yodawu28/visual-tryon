"""
Semantic Parser API endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
import logging

from src.modules.semantic_parser.openai_client import SemanticParserClient
from src.schemas.requests import VTOAnalysisRequest
from src.schemas.responses import VTOAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# Singleton instance
semantic_parser = SemanticParserClient()


@router.post("/vto-context", response_model=VTOAnalysisResponse)
async def analyze_vto_context(request: VTOAnalysisRequest, http_request: Request):
    """
    Analyze virtual try-on context từ user image và product image.

    **Requirements**:
    - User image MUST be anonymized trước (sử dụng /privacy/anonymize endpoint)
    - Images phải ở format base64
    - Headers: X-User-Consent=true, X-Image-Anonymized=true

    **Returns**:
    - clothing_description: Detailed fabric, form, design
    - body_pose: User posture description
    - inpainting_prompt: Optimized prompt for image generation
    """

    # Verify headers (middleware sẽ check, nhưng double-check ở đây)
    # TODO: Re-enable for production
    # consent = http_request.headers.get("X-User-Consent")
    # anonymized = http_request.headers.get("X-Image-Anonymized")

    # if consent != "true":
    #     raise HTTPException(
    #         status_code=403,
    #         detail="User consent required. Please acknowledge privacy policy.",
    #     )

    # if anonymized != "true":
    #     raise HTTPException(
    #         status_code=403,
    #         detail="Image must be anonymized before analysis. Use /privacy/anonymize endpoint first.",
    #     )

    try:
        logger.info("Starting VTO context analysis...")

        analysis = semantic_parser.analyze_vto_context(
            user_image_b64=request.anonymized_user_image,
            product_image_b64=request.product_image,
        )

        logger.info("VTO context analysis completed successfully")

        return VTOAnalysisResponse(
            success=True, analysis=analysis, message="Analysis completed successfully"
        )

    except ValueError as e:
        # OpenAI parsing errors
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
