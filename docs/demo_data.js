window.DEMO_DATA = {
  "disclaimer": "Synthetic demo data only. The pipeline ranks and orders work; a human reviews every output before anything is used.",
  "summary": {
    "total": 30,
    "resolved_suppressed": 6,
    "gated": 11,
    "in_batch_duplicates": 4,
    "in_queue": 9
  },
  "queue": [
    {
      "rank": 1,
      "score": 93.3,
      "company": "Tidewater Software",
      "title": "Backend Engineer I",
      "matched_skills": [
        "Python",
        "Go",
        "SQL",
        "AWS",
        "Kubernetes",
        "REST APIs",
        "Git",
        "CI/CD"
      ],
      "min_years_experience": 1,
      "url": "https://boards.example.test/tidewater/9001",
      "lane": 1,
      "lane_name": "FAST-APPLY",
      "lane_reason": "score 93.3 at or above 70"
    },
    {
      "rank": 2,
      "score": 80.0,
      "company": "Lumen Orbital",
      "title": "Software Engineer, New Grad",
      "matched_skills": [
        "Python",
        "Go",
        "AWS",
        "REST APIs",
        "Git",
        "CI/CD"
      ],
      "min_years_experience": 0,
      "url": "https://alerts.example.test/lumen-orbital/301",
      "lane": 1,
      "lane_name": "FAST-APPLY",
      "lane_reason": "referral bypasses the keyword screen"
    },
    {
      "rank": 3,
      "score": 73.3,
      "company": "Kestrel Security",
      "title": "Platform Engineer, New Grad",
      "matched_skills": [
        "Go",
        "AWS",
        "Kubernetes",
        "Git",
        "CI/CD"
      ],
      "min_years_experience": 0,
      "url": "https://lists.example.test/kestrel/platform",
      "lane": 1,
      "lane_name": "FAST-APPLY",
      "lane_reason": "score 73.3 at or above 70"
    },
    {
      "rank": 4,
      "score": 66.7,
      "company": "Northgate Robotics",
      "title": "Software Engineer, Perception",
      "matched_skills": [
        "Python",
        "Go",
        "Git",
        "CI/CD"
      ],
      "min_years_experience": 0,
      "url": "https://careers.example.test/northgate/p-11",
      "lane": 2,
      "lane_name": "QUICK-TAILOR",
      "lane_reason": "score 66.7 in the 60-70 band where a short tailor can cross the cliff"
    },
    {
      "rank": 5,
      "score": 60.0,
      "company": "Fernwood Games",
      "title": "Software Engineer New Grad 2027",
      "matched_skills": [
        "Python",
        "Git",
        "CI/CD"
      ],
      "min_years_experience": 0,
      "url": "https://lists.example.test/fernwood/new-grad",
      "lane": 2,
      "lane_name": "QUICK-TAILOR",
      "lane_reason": "score 60 in the 60-70 band where a short tailor can cross the cliff"
    },
    {
      "rank": 6,
      "score": 35.0,
      "company": "Harbor Analytics",
      "title": "Data Engineer",
      "matched_skills": [
        "Python",
        "SQL",
        "AWS"
      ],
      "min_years_experience": 2,
      "url": "https://alerts.example.test/harbor/306",
      "lane": 1,
      "lane_name": "FAST-APPLY",
      "lane_reason": "referral bypasses the keyword screen"
    },
    {
      "rank": 7,
      "score": 35.0,
      "company": "Northgate Robotics",
      "title": "Machine Learning Engineer",
      "matched_skills": [
        "Python",
        "AWS",
        "Kubernetes"
      ],
      "min_years_experience": 0,
      "url": "https://careers.example.test/northgate/p-13",
      "lane": 0,
      "lane_name": "SKIP",
      "lane_reason": "score 35 below 60 and no referral"
    },
    {
      "rank": 8,
      "score": 28.3,
      "company": "Ironbark Data",
      "title": "Data Engineer I",
      "matched_skills": [
        "Python",
        "SQL"
      ],
      "min_years_experience": 1,
      "url": "https://lists.example.test/ironbark/de1",
      "lane": 0,
      "lane_name": "SKIP",
      "lane_reason": "score 28.3 below 60 and no referral"
    },
    {
      "rank": 9,
      "score": 15.0,
      "company": "Northgate Robotics",
      "title": "Facilities Technician",
      "matched_skills": [],
      "min_years_experience": 2,
      "url": "https://careers.example.test/northgate/p-17",
      "lane": 0,
      "lane_name": "SKIP",
      "lane_reason": "score 15 below 60 and no referral"
    }
  ],
  "gated": {
    "count": 11,
    "rows": [
      {
        "company": "Quill Systems",
        "title": "Machine Learning Engineer",
        "url": "https://alerts.example.test/quill/303",
        "failed_gate": "min_yoe",
        "reason": "stated floor 3y above candidate ceiling 2y"
      },
      {
        "company": "Brightfield Labs",
        "title": "Platform Engineer",
        "url": "https://alerts.example.test/brightfield/304",
        "failed_gate": "min_yoe",
        "reason": "stated floor 4y above candidate ceiling 2y"
      },
      {
        "company": "Vantage Ledger",
        "title": "Backend Engineer",
        "url": "https://alerts.example.test/vantage/305",
        "failed_gate": "location",
        "reason": "location 'London, UK' not in candidate's allowed set"
      },
      {
        "company": "Zephyr Freight",
        "title": "Principal Software Engineer",
        "url": "https://alerts.example.test/zephyr/307",
        "failed_gate": "min_yoe",
        "reason": "stated floor 10y above candidate ceiling 2y"
      },
      {
        "company": "Marlow Cloud",
        "title": "Software Engineer, Infrastructure",
        "url": "https://boards.example.test/marlow/9003",
        "failed_gate": "work_authorization",
        "reason": "no sponsorship offered"
      },
      {
        "company": "Sable AI",
        "title": "ML Platform Engineer",
        "url": "https://boards.example.test/sable/9004",
        "failed_gate": "clearance",
        "reason": "clearance required"
      },
      {
        "company": "Orchid Cloud",
        "title": "Staff Software Engineer",
        "url": "https://boards.example.test/orchid/9007",
        "failed_gate": "min_yoe",
        "reason": "stated floor 8y above candidate ceiling 2y"
      },
      {
        "company": "Greenleaf Logistics",
        "title": "Warehouse Operations Coordinator",
        "url": "https://boards.example.test/greenleaf/9008",
        "failed_gate": "min_yoe",
        "reason": "stated floor 5y above candidate ceiling 2y"
      },
      {
        "company": "Pinecrest Health",
        "title": "Backend Engineer",
        "url": "https://lists.example.test/pinecrest/be",
        "failed_gate": "min_yoe",
        "reason": "stated floor 3y above candidate ceiling 2y"
      },
      {
        "company": "Northgate Robotics",
        "title": "Data Engineer, Telemetry",
        "url": "https://careers.example.test/northgate/p-12",
        "failed_gate": "min_yoe",
        "reason": "stated floor 3y above candidate ceiling 2y"
      },
      {
        "company": "Northgate Robotics",
        "title": "Senior Software Engineer, Autonomy",
        "url": "https://careers.example.test/northgate/p-16",
        "failed_gate": "min_yoe",
        "reason": "stated floor 7y above candidate ceiling 2y"
      }
    ]
  },
  "sources": [
    {
      "name": "linkedin_alerts",
      "count": 8
    },
    {
      "name": "job_boards",
      "count": 8
    },
    {
      "name": "github_lists",
      "count": 7
    },
    {
      "name": "company_careers",
      "count": 7
    }
  ],
  "routing_tiers": [
    {
      "task": "score",
      "model_tier": "small",
      "note": "runs once per posting; a rough fit estimate is enough to rank the queue"
    },
    {
      "task": "tailor",
      "model_tier": "medium",
      "note": "runs once per posting a person chose to pursue; bounded edit, not free generation"
    },
    {
      "task": "deep_tailor",
      "model_tier": "large",
      "note": "runs rarely, only for postings worth the most careful generation"
    }
  ]
};
