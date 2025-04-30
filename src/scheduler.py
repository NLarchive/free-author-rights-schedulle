import logging
from datetime import date, timedelta
from typing import Optional, List, Dict, Tuple

from .data_models import Work, Author, Jurisdiction, CopyrightRule
from .config import DEFAULT_TERM_YEARS
from . import database
from .date_provider import get_current_date

logger = logging.getLogger(__name__)

def calculate_expiry(work: Work, jurisdiction: Optional[Jurisdiction] = None) -> Optional[date]:
    """
    Calculates the estimated copyright expiry date for a work in a specific jurisdiction.
    If no jurisdiction is provided, uses the work's primary jurisdiction or a default calculation.
    
    Returns the estimated expiry date or None if it cannot be calculated.
    """
    logger.debug(f"Calculating expiry for work: {work.title}")
    
    # If no jurisdiction provided, use work's primary jurisdiction
    if not jurisdiction and work.primary_jurisdiction:
        jurisdiction = work.primary_jurisdiction
    
    # If we have a jurisdiction with special rules, try to apply them
    if jurisdiction and jurisdiction.has_special_rules:
        expiry_date = apply_special_rules(work, jurisdiction)
        if expiry_date:
            return expiry_date
    
    # If no special rules apply or no jurisdiction specified, use standard calculation
    return calculate_standard_expiry(work, jurisdiction)

def calculate_standard_expiry(work: Work, jurisdiction: Optional[Jurisdiction] = None) -> Optional[date]:
    """
    Calculates copyright expiry using the standard "life + X years" rule.
    This is the most common rule internationally.
    """
    # Determine the term years to use
    term_years = DEFAULT_TERM_YEARS
    if jurisdiction:
        term_years = jurisdiction.term_years_after_death
    
    # For works with authors, base calculation on the death date of the last surviving author
    if work.authors:
        latest_death_date: Optional[date] = None
        all_authors_have_death_dates = True
        
        for author in work.authors:
            if author.death_date:
                if latest_death_date is None or author.death_date > latest_death_date:
                    latest_death_date = author.death_date
            else:
                all_authors_have_death_dates = False
        
        if latest_death_date:
            # Common rule: End of the year, X years after the author's death
            expiry_year = latest_death_date.year + term_years
            expiry_date = date(expiry_year, 12, 31)
            
            jur_info = f" in {jurisdiction.name}" if jurisdiction else ""
            logger.info(f"Estimated expiry for '{work.title}' based on life + {term_years} years{jur_info}: {expiry_date}")
            return expiry_date
        
        # If any author's death date is unknown and this is the only basis for calculation
        if not all_authors_have_death_dates and not work.creation_date:
            logger.warning(f"Cannot reliably calculate expiry for '{work.title}': Author death date(s) unknown.")
            return None
    
    # Fall back to creation or publication date if available
    if work.creation_date:
        # Different jurisdictions handle this differently
        # For now, use a common approach for works where author is unknown or corporate
        if jurisdiction:
            # For US corporate works, 95 years from publication or 120 from creation
            if jurisdiction.code == "US":
                term_years = 95
            # For EU anonymous works, 70 years from publication
            elif jurisdiction.code == "EU":
                term_years = 70
        else:
            # Default to a conservative estimate
            term_years = 95
        
        expiry_year = work.creation_date.year + term_years
        expiry_date = date(expiry_year, 12, 31)
        
        jur_info = f" in {jurisdiction.name}" if jurisdiction else ""
        logger.info(f"Estimated expiry for '{work.title}' based on creation + {term_years} years{jur_info}: {expiry_date}")
        return expiry_date
    
    # Cannot determine expiry date with available information
    logger.warning(f"Cannot calculate expiry for '{work.title}': Insufficient information")
    return None

def apply_special_rules(work: Work, jurisdiction: Jurisdiction) -> Optional[date]:
    """
    Applies special copyright rules for a specific jurisdiction.
    Returns the expiry date if a special rule applies, otherwise None.
    """
    if not jurisdiction.id:
        return None
    
    # Get special rules for this jurisdiction
    rules = database.get_copyright_rules_for_jurisdiction(jurisdiction.id)
    if not rules:
        return None
    
    # Apply US-specific rules
    if jurisdiction.code == "US":
        # Rule: Works published before 1923 are in the public domain in the US
        if work.creation_date and work.creation_date.year < 1923:
            for rule in rules:
                if rule.rule_type == "published_before_1923":
                    logger.info(f"'{work.title}' is in public domain in US (published before 1923)")
                    return date(1923, 1, 1)  # Already expired
        
        # Rule: Works published 1923-1977 with notice: 95 years from publication
        if work.creation_date and 1923 <= work.creation_date.year <= 1977:
            for rule in rules:
                if rule.rule_type == "published_1923_to_1977":
                    expiry_year = work.creation_date.year + rule.term_years
                    expiry_date = date(expiry_year, 12, 31)
                    logger.info(f"'{work.title}' expires on {expiry_date} in US (published 1923-1977)")
                    return expiry_date
        
        # Rule: Corporate works/works for hire
        if work.authors and len(work.authors) == 1 and work.authors[0].name.endswith(" Inc."):
            for rule in rules:
                if rule.rule_type == "corporate_works" and work.creation_date:
                    expiry_year = work.creation_date.year + rule.term_years
                    expiry_date = date(expiry_year, 12, 31)
                    logger.info(f"'{work.title}' expires on {expiry_date} in US (corporate work)")
                    return expiry_date
    
    # Apply EU-specific rules
    elif jurisdiction.code == "EU":
        # Rule: Anonymous works
        if not work.authors and work.creation_date:
            for rule in rules:
                if rule.rule_type == "anonymous_works":
                    expiry_year = work.creation_date.year + rule.term_years
                    expiry_date = date(expiry_year, 12, 31)
                    logger.info(f"'{work.title}' expires on {expiry_date} in EU (anonymous work)")
                    return expiry_date
        
        # Rule: Collaborative works
        if len(work.authors) > 1:
            for rule in rules:
                if rule.rule_type == "collaborative_works":
                    # Need death date of last surviving author
                    latest_death_date = None
                    all_authors_have_death_dates = True
                    
                    for author in work.authors:
                        if author.death_date:
                            if latest_death_date is None or author.death_date > latest_death_date:
                                latest_death_date = author.death_date
                        else:
                            all_authors_have_death_dates = False
                    
                    if latest_death_date and all_authors_have_death_dates:
                        expiry_year = latest_death_date.year + rule.term_years
                        expiry_date = date(expiry_year, 12, 31)
                        logger.info(f"'{work.title}' expires on {expiry_date} in EU (collaborative work)")
                        return expiry_date
    
    # Apply UK-specific rules
    elif jurisdiction.code == "GB":
        # Rule: Crown copyright
        if work.authors and any(author.name == "Crown" for author in work.authors) and work.creation_date:
            for rule in rules:
                if rule.rule_type == "crown_copyright":
                    expiry_year = work.creation_date.year + rule.term_years
                    expiry_date = date(expiry_year, 12, 31)
                    logger.info(f"'{work.title}' expires on {expiry_date} in UK (Crown copyright)")
                    return expiry_date
    
    # No special rules applied
    return None

def determine_status(work: Work, jurisdiction: Optional[Jurisdiction] = None, current_date: Optional[date] = None) -> str:
    """
    Determines the copyright status of a work based on its expiry date.
    
    Args:
        work: The work to check
        jurisdiction: The jurisdiction to check in (optional)
        current_date: The date to compare against (defaults to today)
        
    Returns:
        Status string: 'Public Domain', 'Copyrighted', or 'Unknown'
    """
    if current_date is None:
        current_date = get_current_date()
    
    # If work already has a status and no jurisdiction specified, use it
    if not jurisdiction and work.status and work.status != 'Unknown':
        return work.status
    
    # Calculate expiry date for the specified jurisdiction if not already set
    expiry_date = None
    
    if jurisdiction and work.status_by_jurisdiction and jurisdiction.code in work.status_by_jurisdiction:
        # Use the already determined status for this jurisdiction
        return work.status_by_jurisdiction[jurisdiction.code]
    else:
        expiry_date = calculate_expiry(work, jurisdiction)
    
    # If we have an expiry date, compare it to current date
    if expiry_date:
        if expiry_date <= current_date:
            return 'Public Domain'
        else:
            return 'Copyrighted'
    
    # Special case for very old works
    if work.creation_date:
        # Most jurisdictions consider works published before 1875 to be in public domain
        if work.creation_date.year < 1875:
            return 'Public Domain'
        
        # US-specific: works published before 1927 are public domain in the US
        if jurisdiction and jurisdiction.code == 'US' and work.creation_date.year < 1927:
            return 'Public Domain'
    
    # Default case when we can't determine
    return 'Unknown'

def calculate_multi_jurisdiction_status(work: Work, jurisdictions: Optional[List[Jurisdiction]] = None) -> Dict[str, str]:
    """
    Calculates the copyright status of a work across multiple jurisdictions.
    
    Args:
        work: The work to check
        jurisdictions: List of jurisdictions to check (if None, checks all available)
        
    Returns:
        Dictionary mapping jurisdiction codes to status strings
    """
    if not jurisdictions:
        jurisdictions = database.get_all_jurisdictions()
    
    status_map = {}
    
    for jurisdiction in jurisdictions:
        if not jurisdiction.code:
            continue
            
        status = determine_status(work, jurisdiction)
        status_map[jurisdiction.code] = status
        
        # Also store in database for future reference
        if work.id and jurisdiction.id:
            expiry_date = calculate_expiry(work, jurisdiction)
            database.set_work_copyright_status_by_jurisdiction(work.id, jurisdiction.id, status, expiry_date)
    
    return status_map

def update_work_status(work: Work) -> Work:
    """
    Updates a work's copyright status and expiry date across all jurisdictions.
    
    This function:
    1. Calculates the expiry date if not already set
    2. Determines the status based on the expiry date
    3. Calculates status for all major jurisdictions
    4. Returns the updated work
    
    This is useful for updating works after initial creation or when 
    more information becomes available.
    """
    # Get all jurisdictions
    jurisdictions = database.get_all_jurisdictions()
    
    # Calculate global status (no specific jurisdiction)
    if not work.copyright_expiry_date:
        work.copyright_expiry_date = calculate_expiry(work, None)
    
    # Determine primary status
    work.status = determine_status(work)
    
    # Calculate status for all major jurisdictions
    work.status_by_jurisdiction = calculate_multi_jurisdiction_status(work, jurisdictions)
    
    # Update primary jurisdiction if not set but we have author nationality
    if not work.primary_jurisdiction and work.authors:
        for author in work.authors:
            if author.nationality:
                # Try to find matching jurisdiction
                for jurisdiction in jurisdictions:
                    if jurisdiction.code == author.nationality:
                        work.primary_jurisdiction = jurisdiction
                        break
                if work.primary_jurisdiction:
                    break
    
    return work

def get_days_until_expiry(work, jurisdiction: Optional[Jurisdiction] = None, current_date: Optional[date] = None) -> Optional[int]:
    """
    Calculates the number of days until a work's copyright expires in a given jurisdiction.
    
    Returns None if the work's expiry date is unknown or if it's already
    in the public domain.
    """
    if current_date is None:
        current_date = get_current_date()
    
    # Calculate expiry date for the specified jurisdiction
    expiry_date = None
    
    if jurisdiction:
        expiry_date = calculate_expiry(work, jurisdiction)
    else:
        if not work.copyright_expiry_date:
            work.copyright_expiry_date = calculate_expiry(work, None)
        expiry_date = work.copyright_expiry_date
    
    if not expiry_date:
        return None
    
    # Check if already in public domain
    status = determine_status(work, jurisdiction, current_date)
    if status == 'Public Domain':
        return None
    
    days = (expiry_date - current_date).days
    return days if days >= 0 else None

def get_works_by_status_in_jurisdiction(jurisdiction_code: str, status: str) -> List[Work]:
    """
    Returns a list of works with a specific status in a specific jurisdiction.
    
    Args:
        jurisdiction_code: The two-letter code of the jurisdiction (e.g., 'US', 'EU')
        status: The status to filter by ('Public Domain', 'Copyrighted', 'Unknown')
        
    Returns:
        A list of Work objects with the specified status in the jurisdiction
    """
    # Get the jurisdiction
    jurisdiction = None
    for j in database.get_all_jurisdictions():
        if j.code == jurisdiction_code:
            jurisdiction = j
            break
    
    if not jurisdiction:
        logger.warning(f"Unknown jurisdiction code: {jurisdiction_code}")
        return []
    
    # Get all works from the database
    all_works = database.get_all_works()
    
    # Filter works by status in the specified jurisdiction
    matching_works = []
    for work in all_works:
        work_status = determine_status(work, jurisdiction)
        if work_status == status:
            matching_works.append(work)
    
    return matching_works
