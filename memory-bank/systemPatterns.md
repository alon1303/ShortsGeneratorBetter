# System Patterns: ShortsGenerator Automation Pipeline

## System Architecture

### High-Level Architecture Overview
The ShortsGenerator Automation Pipeline follows a **modular, component-based architecture** with clear separation of concerns. The system is organized into four main layers:

1. **Orchestration Layer** (`auto_pipeline.py`): Coordinates the entire workflow
2. **Content Layer** (`reddit_story/`): Handles content fetching and processing
3. **Processing Layer** (`video_composer.py`, `tts_router.py`): Converts content to videos
4. **Publishing Layer** (`youtube/uploader.py`): Manages YouTube uploads and metadata

### Component Relationships
```
AutoPipeline (Orchestrator)
├── RedditClient (Content Fetcher)
├── StoryProcessor (Content Processor)
├── VideoComposer (Video Generator)
└── YouTubeUploader (Publisher)
```

## Key Technical Decisions

### 1. Asynchronous-First Design
- **Decision**: Use asyncio for all I/O operations
- **Rationale**: Better concurrency for API calls and file operations
- **Implementation**: All components expose async methods
- **Benefits**: Non-blocking operations, efficient resource usage

### 2. Modular Component Design
- **Decision**: Separate concerns into independent modules
- **Rationale**: Easier testing, maintenance, and extension
- **Implementation**: Each major function in separate class/file
- **Benefits**: Code reuse, isolated failures, clear interfaces

### 3. Configuration Centralization
- **Decision**: Single configuration source (`config/settings.py`)
- **Rationale**: Consistent settings across all components
- **Implementation**: Pydantic Settings with environment variable support
- **Benefits**: Type safety, validation, easy deployment configuration

### 4. Stateless with Persistent State Tracking
- **Decision**: Components are stateless but track state in JSON files
- **Rationale**: Crash recovery and monitoring
- **Implementation**: `processed_posts.json`, `pipeline_stats.json`, cycle logs
- **Benefits**: Resumable operations, failure analysis, statistics tracking

### 5. Graceful Degradation
- **Decision**: Individual story failures don't stop pipeline
- **Rationale**: Maximize throughput despite intermittent failures
- **Implementation**: Try/except per story with retry logic
- **Benefits**: Higher success rates, continuous operation

## Design Patterns in Use

### 1. Pipeline Pattern
- **Pattern**: Sequential processing pipeline
- **Implementation**: `AutoPipeline.run_single_cycle()` orchestrates: Fetch → Process → Generate → Upload
- **Use Case**: End-to-end story transformation

### 2. Strategy Pattern
- **Pattern**: Interchangeable algorithms
- **Implementation**: `tts_router.py` supports multiple TTS engines (Edge, ElevenLabs)
- **Use Case**: Different TTS providers based on configuration

### 3. Builder Pattern
- **Pattern**: Step-by-step object construction
- **Implementation**: `VideoComposer` builds videos from components (audio, background, subtitles)
- **Use Case**: Complex video assembly with multiple elements

### 4. Repository Pattern
- **Pattern**: Data access abstraction
- **Implementation**: `RedditClient` abstracts Reddit API access
- **Use Case**: Story fetching with caching and duplicate prevention

### 5. Decorator Pattern
- **Pattern**: Add functionality to objects dynamically
- **Implementation**: `AsyncYouTubeUploader` wraps `YouTubeUploader` for async operations
- **Use Case**: Adapt blocking APIs to async environment

### 6. Observer Pattern
- **Pattern**: Event notification system
- **Implementation**: Logging and statistics tracking across pipeline
- **Use Case**: Monitoring and error reporting

## Critical Implementation Paths

### Main Execution Path
1. **Pipeline Initialization** (`AutoPipeline.initialize()`)
   - Load configuration
   - Authenticate YouTube API
   - Initialize Reddit client

2. **Story Fetching** (`AutoPipeline.fetch_stories()`)
   - Query multiple subreddits
   - Filter by score, length, duplicates
   - Return eligible stories

3. **Story Processing** (`AutoPipeline.process_story()`)
   - Split story into parts
   - Generate title card
   - Create TTS audio
   - Generate video parts
   - Concatenate final video

4. **YouTube Upload** (`AutoPipeline.upload_to_youtube_if_enabled()`)
   - Rate limit checking
   - Generate metadata
   - Upload video
   - Handle quota errors

### Error Recovery Path
1. **Retry Logic** (`AutoPipeline.process_story_with_retry()`)
   - Exponential backoff (30s, 60s, 90s)
   - Different retry strategies per error type
   - Maximum retries configurable

2. **Error Classification** (`PipelineStats.add_error()`)
   - Network errors (retry)
   - Processing errors (log and skip)
   - Quota errors (stop or continue)
   - Upload errors (retry with delay)

### State Persistence Path
1. **Duplicate Prevention** (`RedditClient.mark_post_as_processed()`)
   - Append to `processed_posts.json`
   - Memory cache with periodic flush

2. **Statistics Tracking** (`PipelineStats.save_stats()`)
   - Update `pipeline_stats.json`
   - Track success rates, durations, error types

3. **Cycle Logging** (`AutoPipeline._save_cycle_results()`)
   - Save individual cycle results
   - JSON format for analysis

## Component Interfaces

### AutoPipeline Interface
```python
class AutoPipeline:
    async def initialize() -> bool
    async def fetch_stories() -> List[RedditStory]
    async def process_story(story: RedditStory) -> Optional[Path]
    async def upload_to_youtube_if_enabled(video_path: Path, story: RedditStory) -> Optional[YouTubeUploadResult]
    async def run_single_cycle() -> Dict[str, Any]
    async def run_continuous(interval_minutes: int, max_cycles: Optional[int])
```

### RedditClient Interface
```python
class RedditClient:
    async def initialize() -> bool
    async def fetch_trending_stories(subreddit: List[str], **filters) -> List[RedditStory]
    def mark_post_as_processed(post_id: str)
    async def close()
```

### YouTubeUploader Interface
```python
class YouTubeUploader:
    def get_authenticated_service() -> Optional[Any]
    def upload_video(video_path: Path, **metadata) -> YouTubeUploadResult
    def validate_credentials() -> bool
    def generate_default_tags(subreddit: str, story_title: str) -> List[str]
    def generate_description(**story_info) -> str
```

## Data Flow Patterns

### Story Data Flow
1. **Raw Story** → `RedditStory` object
2. **RedditStory** → `ProcessedStory` (split into parts)
3. **ProcessedStory** → Audio chunks + timing data
4. **Audio + Background** → Video parts
5. **Video parts** → Final concatenated video

### Metadata Flow
1. **Reddit metadata** (title, subreddit, score, URL)
2. **Processing metadata** (part count, durations, success/failure)
3. **YouTube metadata** (title, description, tags, privacy)
4. **Statistics metadata** (timestamps, error types, durations)

### Error Flow
1. **Component error** → Exception caught
2. **Exception** → Logged with stack trace
3. **Error type** → Classified (network, processing, upload, quota)
4. **Error stats** → Tracked in `PipelineStats`
5. **Recovery** → Retry or skip based on error type

## Integration Patterns

### API Integration Pattern
- **Pattern**: Adapter + Circuit Breaker
- **Implementation**: Wrapper classes with retry logic
- **Examples**: RedditClient, YouTubeUploader
- **Features**: Rate limiting, error handling, caching

### File Processing Pattern
- **Pattern**: Producer-Consumer with temporary files
- **Implementation**: Generate intermediate files, clean up after processing
- **Examples**: Audio generation, video composition
- **Features**: Disk space management, cleanup routines

### Configuration Pattern
- **Pattern**: Singleton with environment overrides
- **Implementation**: `Settings` class with pydantic validation
- **Features**: Type safety, default values, environment variable support

## Scalability Considerations

### Horizontal Scaling
- **Current**: Single instance processing
- **Potential**: Multiple instances with different subreddits
- **Challenges**: Duplicate prevention synchronization
- **Solution**: Centralized duplicate tracking (Redis, database)

### Resource Management
- **CPU**: Video generation is intensive
- **Memory**: Large video files in memory
- **Disk**: Temporary and final video storage
- **Network**: API rate limits and quotas

### Performance Optimization
- **Bottlenecks**: TTS generation, video rendering
- **Optimizations**: Caching, parallel processing where possible
- **Monitoring**: Track processing times, identify slow components

## Testing Patterns

### Unit Testing
- **Pattern**: Mock external dependencies
- **Focus**: Individual component logic
- **Tools**: pytest, unittest, mocks

### Integration Testing
- **Pattern**: Test component interactions
- **Focus**: End-to-end flow without YouTube upload
- **Tools**: `--no-upload` flag, test files

### Performance Testing
- **Pattern**: Long-running stability tests
- **Focus**: Memory leaks, crash recovery
- **Tools**: `--cycles` parameter, memory profiling

### Regression Testing
- **Pattern**: Test known failure scenarios
- **Focus**: Error handling, edge cases
- **Tools**: Test fixtures, error injection

## Deployment Patterns

### Development Environment
- **Pattern**: Local execution with full stack
- **Requirements**: Python 3.8+, FFmpeg, dependencies
- **Setup**: `pip install -r requirements.txt`

### Production Environment
- **Pattern**: Headless server with monitoring
- **Requirements**: Stable internet, sufficient disk space
- **Monitoring**: Log files, statistics, error alerts

### Configuration Management
- **Pattern**: Environment variables + .env file
- **Security**: Keep `client_secrets.json` secure
- **Updates**: Version control for configuration changes

## Known Architecture Limitations

### 1. Single-Threaded Processing
- **Limitation**: Stories processed sequentially
- **Impact**: Limits throughput to ~3 stories/hour
- **Mitigation**: Could parallelize with careful resource management

### 2. Local File Storage
- **Limitation**: All videos stored locally
- **Impact**: Disk space consumption
- **Mitigation**: Periodic cleanup, cloud storage option

### 3. YouTube Quota Limits
- **Limitation**: ~6 uploads/day maximum
- **Impact**: Limits scalability
- **Mitigation**: Multiple YouTube accounts, quota management

### 4. No Distributed State
- **Limitation**: JSON files for state tracking
- **Impact**: Single instance only, no failover
- **Mitigation**: Database backend for distributed processing

## Future Architecture Directions

### 1. Microservices Architecture
- **Direction**: Separate services for Reddit, TTS, Video, YouTube
- **Benefits**: Independent scaling, polyglot implementation
- **Challenges**: Service coordination, data consistency

### 2. Cloud-Native Deployment
- **Direction**: Containerized services on Kubernetes
- **Benefits**: Auto-scaling, high availability
- **Challenges**: Cost, complexity

### 3. Event-Driven Architecture
- **Direction**: Message queues for pipeline steps
- **Benefits**: Better decoupling, fault tolerance
- **Challenges**: Message ordering, delivery guarantees

### 4. Multi-Platform Publishing
- **Direction**: Extend beyond YouTube to TikTok, Instagram
- **Benefits**: Increased reach, redundancy
- **Challenges**: Platform-specific requirements