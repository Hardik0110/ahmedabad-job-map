from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    domain = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    location_text = Column(String)
    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_companies_name", "name"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String, nullable=False)
    experience = Column(String)
    url = Column(String)
    source = Column(String)  # "naukri" | "linkedin" | "indeed"
    scraped_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_company_id", "company_id"),
        Index("idx_jobs_source", "source"),
    )
