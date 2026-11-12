T2I_RUBRICS = {
    "object_entity": {
        "name": "Object/Entity Accuracy",
        "description": (
            "Correct number of objects present, correct number of entities, "
            "no hallucinated objects, correct object attributes (color, type, size, etc.)"
        ),
        "scale": {
            1: "Severe inaccuracies, image completely inaccurate/nonsensical",
            2: "Moderate-to-severe inaccuracies, serious inconsistencies",
            3: "1-2 rules broken, slight inconsistency, image coherent",
            4: "0-1 rules broken, very slight inaccuracies, still coherent",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "action_event": {
        "name": "Action/Event Accuracy",
        "description": (
            "Action matches text description, action stage/progress correct, "
            "spatial relationships match, scene setting matches"
        ),
        "scale": {
            1: "Image is completely inaccurate",
            2: "Serious inconsistencies that significantly affect accuracy",
            3: "Image coherent, clearly visible inconsistencies",
            4: "Coherent/acceptable, slight ambiguity/inaccuracy",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "semantic_completeness": {
        "name": "Semantic Completeness",
        "description": (
            "All elements from text are present in image, no missing components, "
            "context appropriately depicted"
        ),
        "scale": {
            1: "Massively incomplete – key component(s) missing",
            2: "Incomplete – some key components missing",
            3: "Some non-key components missing, partial context",
            4: "Small/minor elements missing",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
}

I2I_RUBRICS = {
    "identity_preservation": {
        "name": "Identity Preservation",
        "description": (
            "Character/object identity maintained, consistent appearance "
            "(color, clothing, features), consistent style, consistent objects. "
            "NOTE: Changes that follow the story narrative are NOT problematic."
        ),
        "scale": {
            1: "Large shifts in identity/appearance/style",
            2: "Moderate-to-large shifts",
            3: "Moderate shifts",
            4: "Small/minor shifts",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "spatial_temporal_continuity": {
        "name": "Spatial/Temporal Continuity",
        "description": (
            "Logical transitions between images, logical movement transitions, "
            "logical perspective/camera transitions"
        ),
        "scale": {
            1: "Images catastrophically disconnected",
            2: "Moderate-to-large disconnect, abrupt/jarring transitions",
            3: "Moderate disconnect, abrupt but passable",
            4: "Small/minor disconnect, does not affect continuity severely",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "quality_consistency": {
        "name": "Quality Consistency",
        "description": (
            "Resolution quality consistent, no sudden artifact introduction, "
            "detail consistency"
        ),
        "scale": {
            1: "Severe quality issues, large visual artifacts",
            2: "Moderate-to-large quality change / artifacts",
            3: "Moderate but passable quality change",
            4: "Small/minor quality change",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "visual_complexity": {
        "name": "Visual Complexity",
        "description": (
            "Style continuity, luminosity & contrast consistency, "
            "color palette consistency, detail level consistency"
        ),
        "scale": {
            1: "Extreme / inappropriate style shifts, jarring changes",
            2: "Large style inconsistencies that disrupt visual flow",
            3: "Moderate style shifts that don't break sequence",
            4: "Minor style variations that maintain coherence",
            5: "Very minor / subjective variations",
            6: "Consistent style throughout, coherent aesthetic",
        },
    },
}

SEQUENCE_RUBRICS = {
    "sequencing": {
        "name": "Sequencing",
        "description": "Are the images in a logical temporal order?",
        "choices": ("yes", "no"),
    },
    "plausibility": {
        "name": "Plausibility",
        "description": "Is this a plausible real-world temporal event sequence?",
        "choices": ("yes", "no"),
    },
    "narrative_coherence": {
        "name": "Narrative Coherence",
        "description": (
            "Logical progression maintained, goal achieved, "
            "causal relationships preserved"
        ),
        "scale": {
            1: "No logical progression, incoherent",
            2: "Major coherence issues",
            3: "Moderate issues, passable",
            4: "Minor issues, mostly coherent",
            5: "Very minor / subjective issues",
            6: "Successful / Pass",
        },
    },
    "visual_complexity_narrative": {
        "name": "Visual Complexity (Narrative)",
        "description": (
            "Style coherence across the full sequence, aesthetic supports storytelling, "
            "style/perspective shifts make sense for content"
        ),
        "scale": {
            1: "Extreme style shifts across the sequence",
            2: "Large inconsistencies across multiple images",
            3: "Moderate shifts",
            4: "Minor variations maintaining coherence",
            5: "Very minor / subjective variations",
            6: "Perfect consistency, shifts enhance narrative",
        },
    },
}


def rubric_sections(example):
    """Build image, consecutive-pair, and sequence sections in study order."""
    sections = []
    for image in example['images']:
        sections.append({
            'title': f"Text-to-Image · Image {image['image_id']}",
            'eval_type': 't2i', 'eval_target': str(image['image_id']),
            'images': [image], 'rubrics': T2I_RUBRICS,
        })
    for index, image in enumerate(example['images']):
        pair = image.get('pairwise_next')
        if pair:
            sections.append({
                'title': f"Image-to-Image · {pair['image_pair']}",
                'eval_type': 'i2i', 'eval_target': pair['image_pair'],
                'images': [image, example['images'][index + 1]], 'rubrics': I2I_RUBRICS,
            })
    sections.append({
        'title': 'Sequence Evaluation', 'eval_type': 'sequence',
        'eval_target': 'sequence', 'images': example['images'],
        'rubrics': SEQUENCE_RUBRICS,
    })
    return sections


def expected_rating_keys(example):
    """List all required rating keys used to determine example completion."""
    return [
        (section['eval_type'], section['eval_target'], dimension)
        for section in rubric_sections(example)
        for dimension in section['rubrics']
    ]
