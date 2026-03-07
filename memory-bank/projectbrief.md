# Project Brief: ShortsGenerator Automation Pipeline

## Project Overview
ShortsGenerator is an automated content creation pipeline that transforms trending Reddit stories into engaging YouTube Shorts videos. The system fetches viral content from popular subreddits, processes it through AI narration and video generation, and publishes to YouTube with optimized metadata.

## Core Requirements & Goals

### Primary Objectives
1. **Automated Content Pipeline**: Create a fully automated system that runs continuously with minimal human intervention
2. **YouTube Shorts Optimization**: Generate vertical format videos (1080x1920) with proper #shorts metadata
3. **Content Quality**: Ensure videos are engaging with professional narration, subtitles, and visual appeal
4. **Duplicate Prevention**: Track processed posts to avoid re-using content
5. **Error Resilience**: Handle failures gracefully with retry logic and comprehensive logging
6. **YouTube API Integration**: Upload videos with proper titles, descriptions, and tags

### Success Metrics
- High success rate (>80%) for story-to-video conversion
- Average video duration under 3 minutes (YouTube Shorts limit)
- Effective duplicate prevention system
- YouTube upload success with proper metadata
- Comprehensive logging and statistics tracking

## Scope Definition

### In Scope
- **Execution Flow**: Orchestration of the complete pipeline from story fetching to YouTube upload
- **Scheduling**: Interval-based execution with configurable timing between cycles
- **auto_pipeline.py**: Main orchestration engine coordinating all components
- **Logs**: Comprehensive logging system with file and console output
- **Statistics**: Tracking success/failure rates, durations, and error types
- **Configuration**: Settings management via config/settings.py
- **YouTube Upload**: OAuth2 authentication and video upload integration
- **Duplicate Prevention**: Post ID tracking in processed_posts.json

### Out of Scope
- **Core Video Generation**: Video composition, TTS, subtitles are treated as black boxes
- **Background Management**: Background video selection and management
- **Reddit Client Implementation**: Story fetching is considered working
- **Image Generation**: Title card creation is considered working
- **Low-level FFmpeg Operations**: Video processing libraries are assumed functional

## Key Constraints
- **YouTube API Quota**: Limited to ~6 uploads per day (10,000 units)
- **Video Duration**: Must be under 3 minutes for YouTube Shorts
- **Content Safety**: Must exclude NSFW content and respect platform terms
- **Resource Usage**: Video generation is CPU/GPU intensive
- **Network Reliability**: Must handle intermittent connectivity issues

## Timeline & Milestones
- **Phase 1**: Single-cycle operation without YouTube upload (Complete)
- **Phase 2**: YouTube integration with OAuth2 authentication (Complete)
- **Phase 3**: Continuous operation with interval scheduling (Complete)
- **Phase 4**: Error handling and retry logic (Complete)
- **Phase 5**: Statistics tracking and monitoring (Complete)
- **Phase 6**: Production optimization and scaling (Current Focus)

## Stakeholders
- **Primary User**: Content creator seeking automated YouTube Shorts generation
- **Technical Operator**: Developer maintaining and monitoring the pipeline
- **End Viewer**: YouTube audience consuming Shorts content

## Success Criteria
The pipeline is considered successful when it can:
1. Run unattended for 24+ hours without crashing
2. Process 3+ stories per hour successfully
3. Maintain YouTube upload success rate >90%
4. Provide comprehensive logs for debugging
5. Track all statistics for performance monitoring
6. Prevent duplicate content effectively