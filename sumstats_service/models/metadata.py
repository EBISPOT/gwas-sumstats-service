from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from enum import Enum


class EffectStatisticEnum(str, Enum):
    beta = 'beta'
    odds_ratio = 'odds_ratio'
    hazard_ratio = 'hazard_ratio'


class SampleMetadata(BaseModel):
    ancestryMethod: Optional[List[str]] = None
    caseControlStudy: Optional[bool] = None
    caseCount: Optional[int] = None
    controlCount: Optional[int] = None
    sampleSize: int
    sampleAncestry: List[str]


class SumStatsMetadata(BaseModel):
    genotypingTechnology: List[str]
    GWASID: str
    traitDescription: List[str] = None
    effectAlleleFreqLowerLimit: Optional[float] = None
    dataFileName: str
    fileType: str
    dataFileMd5sum: str
    isHarmonised: Optional[bool] = False
    isSorted: Optional[bool] = False
    dateLastModified: date
    genomeAssembly: str
    effectStatistic: Optional[EffectStatisticEnum] = None
    pvalueIsNegLog10: Optional[bool] = False
    analysisSoftware: Optional[str] = None
    imputationPanel: Optional[str] = None
    imputationSoftware: Optional[str] = None
    hmCodeDefinition: Optional[dict] = None
    harmonisationReference: Optional[str] = None
    adjustedCovariates: Optional[str] = None
    ontologyMapping: Optional[str] = None
    authorNotes: Optional[str] = None
    samples: List[SampleMetadata]

    class Config:
        use_enum_values = True  
