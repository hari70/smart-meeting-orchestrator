# strava_client.py - Strava API integration for fitness-aware scheduling

import os
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StravaClient:
    def __init__(self):
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.access_token = os.getenv("STRAVA_ACCESS_TOKEN")
        self.base_url = "https://www.strava.com/api/v3"
        
        if self.access_token:
            logger.info("✅ Strava integration enabled")
        else:
            logger.info("📝 Strava integration disabled - mock data mode")
    
    async def get_athlete_activities(self, limit: int = 5, activity_type: str = None) -> List[Dict]:
        """Get recent athlete activities"""
        
        if not self.access_token:
            # Return mock data for development
            return self._get_mock_activities(limit)
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"per_page": limit}
            
            if activity_type:
                params["type"] = activity_type
            
            response = requests.get(
                f"{self.base_url}/athlete/activities",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                activities = response.json()
                logger.info(f"📊 Retrieved {len(activities)} Strava activities")
                return activities
            else:
                logger.error(f"Strava API error: {response.status_code}")
                return self._get_mock_activities(limit)
                
        except Exception as e:
            logger.error(f"Error fetching Strava activities: {e}")
            return self._get_mock_activities(limit)
    
    async def get_athlete_stats(self, athlete_id: str = None) -> Dict:
        """Get athlete statistics"""
        
        if not self.access_token:
            return self._get_mock_stats()
        
        try:
            # If no athlete_id provided, get current athlete first
            if not athlete_id:
                athlete_id = await self._get_current_athlete_id()
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(
                f"{self.base_url}/athletes/{athlete_id}/stats",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return self._get_mock_stats()
                
        except Exception as e:
            logger.error(f"Error fetching Strava stats: {e}")
            return self._get_mock_stats()
    
    async def _get_current_athlete_id(self) -> str:
        """Get current athlete ID"""
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = requests.get(
            f"{self.base_url}/athlete",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return str(response.json().get("id"))
        
        return "mock_athlete"
    
    def _get_mock_activities(self, limit: int) -> List[Dict]:
        """Generate mock activities for development"""
        
        now = datetime.now()
        mock_activities = []
        
        activity_types = ["Run", "Bike", "Swim", "Hike", "Workout"]
        
        for i in range(min(limit, 5)):
            activity_date = now - timedelta(days=i)
            
            mock_activities.append({
                "id": f"mock_activity_{i}",
                "name": f"Morning {activity_types[i % len(activity_types)]}",
                "type": activity_types[i % len(activity_types)],
                "start_date": activity_date.isoformat() + "Z",
                "elapsed_time": 3600 + (i * 300),  # 1-2 hours
                "distance": 5000 + (i * 1000),  # 5-10km
                "average_heartrate": 140 + (i * 10),  # Varying intensity
                "moving_time": 3600,
                "total_elevation_gain": 100 + (i * 50)
            })
        
        return mock_activities
    
    def _get_mock_stats(self) -> Dict:
        """Generate mock stats for development"""
        
        return {
            "recent_run_totals": {
                "count": 12,
                "distance": 85000,  # meters
                "moving_time": 25200,  # seconds
                "elapsed_time": 26400
            },
            "recent_ride_totals": {
                "count": 8,
                "distance": 150000,
                "moving_time": 18000,
                "elapsed_time": 19800
            },
            "ytd_run_totals": {
                "count": 45,
                "distance": 425000,
                "moving_time": 126000
            },
            "all_time_totals": {
                "count": 234,
                "distance": 2500000,
                "moving_time": 780000
            }
        }
    
    def analyze_workout_patterns(self, activities: List[Dict]) -> Dict:
        """Analyze workout patterns for optimal meeting scheduling"""
        
        if not activities:
            return {"recommendation": "No recent activity data available"}
        
        # Analyze workout timing patterns
        workout_days = []
        high_intensity_count = 0
        
        for activity in activities:
            try:
                activity_date = datetime.fromisoformat(activity["start_date"].replace('Z', '+00:00'))
                workout_days.append(activity_date.strftime("%A"))
                
                # Determine intensity based on heart rate or duration
                heart_rate = activity.get("average_heartrate", 0)
                duration = activity.get("elapsed_time", 0)
                
                if heart_rate > 150 or duration > 5400:  # High HR or >90 min
                    high_intensity_count += 1
                    
            except Exception as e:
                logger.error(f"Error analyzing activity: {e}")
        
        # Find patterns
        common_workout_days = list(set(workout_days))
        high_intensity_ratio = high_intensity_count / len(activities) if activities else 0
        
        # Generate recommendations
        recommendations = []
        
        if "Monday" in common_workout_days:
            recommendations.append("Avoid Monday morning meetings (workout day)")
        if "Wednesday" in common_workout_days:
            recommendations.append("Wednesday afternoons better than mornings")
        if high_intensity_ratio > 0.5:
            recommendations.append("Allow 2+ hours recovery after workouts")
        
        return {
            "workout_days": common_workout_days,
            "high_intensity_ratio": high_intensity_ratio,
            "recommendations": recommendations,
            "optimal_meeting_times": ["Tuesday afternoon", "Thursday morning", "Friday afternoon"]
        }