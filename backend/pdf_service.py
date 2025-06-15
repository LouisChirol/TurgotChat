import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from loguru import logger
from redis_service import redis_service
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def create_chat_pdf(session_id: str) -> Path:
    """Create a PDF file from the chat history of a session."""
    try:
        # Get chat history from Redis
        history = redis_service.get_history(session_id)
        if not history.messages:
            raise HTTPException(status_code=404, detail="No chat history found for this session")

        # Create a temporary file for the PDF
        temp_dir = Path(tempfile.gettempdir())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = temp_dir / f"colbert_chat_{session_id}_{timestamp}.pdf"

        # Create the PDF document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Create styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='UserMessage',
            parent=styles['Normal'],
            textColor=colors.HexColor('#2563EB'),  # Blue-600
            fontSize=11,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='AssistantMessage',
            parent=styles['Normal'],
            textColor=colors.HexColor('#1F2937'),  # Gray-800
            fontSize=11,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='Timestamp',
            parent=styles['Normal'],
            textColor=colors.gray,
            fontSize=8,
            spaceAfter=12
        ))

        # Build the PDF content
        story = []
        
        # Add title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph("Conversation avec Colbert", title_style))
        story.append(Spacer(1, 20))

        # Add disclaimer
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(
            "Cette conversation est un résumé généré automatiquement. "
            "Les informations fournies doivent être vérifiées auprès des sources officielles.",
            disclaimer_style
        ))
        story.append(Spacer(1, 20))

        # Add messages
        for msg in history.messages:
            # Add timestamp
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
            story.append(Paragraph(timestamp, styles['Timestamp']))
            
            # Add message content
            if msg.type == 'human':
                story.append(Paragraph(f"Vous: {msg.content}", styles['UserMessage']))
            else:
                story.append(Paragraph(f"Colbert: {msg.content}", styles['AssistantMessage']))
            
            story.append(Spacer(1, 12))

        # Build the PDF
        doc.build(story)
        logger.info(f"PDF created at {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating PDF file") 