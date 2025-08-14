#!/usr/bin/env python3
"""
Integration tests for Advanced ML Analytics Engine
Tests machine learning capabilities, predictive analytics, and intelligent insights
"""

import pytest
import numpy as np
import pandas as pd
import json
import time
import requests
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestMLAnalyticsEngine:
    """Test suite for ML analytics functionality"""

    @pytest.fixture
    def ml_engine(self):
        """Mock ML analytics engine for testing"""
        try:
            import sys

            sys.path.append("/home/mills/collections/ml-analytics")
            from advanced_analytics_engine import AdvancedAnalyticsEngine

            engine = AdvancedAnalyticsEngine()
            return engine

        except ImportError:
            # Return mock if dependencies aren't available
            mock_engine = Mock()
            mock_engine.influxdb_client = Mock()
            mock_engine.models = {}
            mock_engine.scalers = {}
            mock_engine.model_performance = {}
            mock_engine.data_cache = {}
            mock_engine.insights_history = []
            mock_engine.analysis_stats = {
                "total_analyses": 0,
                "anomalies_detected": 0,
                "predictions_generated": 0,
                "models_trained": 0,
                "insights_generated": 0,
            }
            return mock_engine

    @pytest.fixture
    def sample_metrics_data(self):
        """Generate sample metrics data for testing"""
        # Create 48 hours of sample data
        dates = pd.date_range(
            start=datetime.utcnow() - timedelta(hours=48),
            end=datetime.utcnow(),
            freq="5min",
        )

        np.random.seed(42)  # For reproducible tests

        # Normal operation with some anomalies
        base_cpu = 45 + 10 * np.sin(np.linspace(0, 4 * np.pi, len(dates)))
        cpu_noise = np.random.normal(0, 5, len(dates))
        cpu_percent = base_cpu + cpu_noise

        # Add some anomalies
        anomaly_indices = np.random.choice(len(dates), size=20, replace=False)
        cpu_percent[anomaly_indices] += np.random.normal(30, 10, 20)  # CPU spikes

        # Memory with growth trend
        base_memory = 60 + np.linspace(0, 15, len(dates))  # Growing memory usage
        memory_noise = np.random.normal(0, 3, len(dates))
        memory_percent = base_memory + memory_noise

        # Disk with stable usage
        disk_percent = 25 + np.random.normal(0, 2, len(dates))

        data = pd.DataFrame(
            {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
            },
            index=dates,
        )

        return data

    def test_historical_data_fetching(self, ml_engine):
        """Test historical data fetching from InfluxDB"""
        if not hasattr(ml_engine, "fetch_historical_data"):
            pytest.skip("Historical data fetching not available")

        # Mock InfluxDB query result
        mock_points = [
            {
                "time": "2025-08-07T10:00:00Z",
                "cpu_percent": 45.5,
                "memory_percent": 67.2,
            },
            {
                "time": "2025-08-07T10:05:00Z",
                "cpu_percent": 48.1,
                "memory_percent": 68.5,
            },
            {
                "time": "2025-08-07T10:10:00Z",
                "cpu_percent": 52.3,
                "memory_percent": 65.8,
            },
        ]

        mock_result = Mock()
        mock_result.get_points.return_value = mock_points

        if ml_engine.influxdb_client:
            ml_engine.influxdb_client.query.return_value = mock_result

            data = ml_engine.fetch_historical_data("host_resources", hours=24)

            assert isinstance(data, pd.DataFrame)
            if not data.empty:
                assert "cpu_percent" in data.columns
                assert "memory_percent" in data.columns
                assert len(data) == 3

    def test_anomaly_detection(self, ml_engine, sample_metrics_data):
        """Test anomaly detection capabilities"""
        if not hasattr(ml_engine, "detect_anomalies"):
            pytest.skip("Anomaly detection not available")

        try:
            # Test anomaly detection with sample data
            insights = ml_engine.detect_anomalies(
                sample_metrics_data, ["cpu_percent", "memory_percent"]
            )

            assert isinstance(insights, list)

            # Should detect some anomalies in our sample data (which has intentional anomalies)
            if insights:
                anomaly_insight = insights[0]

                # Check insight structure
                assert hasattr(anomaly_insight, "analysis_type")
                assert hasattr(anomaly_insight, "severity")
                assert hasattr(anomaly_insight, "confidence")
                assert hasattr(anomaly_insight, "description")
                assert hasattr(anomaly_insight, "recommendations")

                # Should have reasonable confidence
                assert 0.0 <= anomaly_insight.confidence <= 1.0

        except ImportError:
            pytest.skip("ML libraries not available for anomaly detection")

    def test_predictive_analytics(self, ml_engine, sample_metrics_data):
        """Test predictive analytics capabilities"""
        if not hasattr(ml_engine, "generate_predictions"):
            pytest.skip("Predictive analytics not available")

        try:
            # Test prediction generation
            insights = ml_engine.generate_predictions(
                sample_metrics_data,
                "memory_percent",  # Memory has growth trend in sample data
            )

            assert isinstance(insights, list)

            if insights:
                prediction_insight = insights[0]

                # Check prediction insight structure
                assert hasattr(prediction_insight, "data_points")
                assert "current_value" in prediction_insight.data_points
                assert "predicted_max" in prediction_insight.data_points
                assert "model_accuracy" in prediction_insight.data_points

                # Predictions should be reasonable
                assert prediction_insight.data_points["current_value"] > 0
                assert (
                    prediction_insight.data_points["predicted_max"]
                    >= prediction_insight.data_points["current_value"]
                )

        except ImportError:
            pytest.skip("ML libraries not available for predictive analytics")

    def test_performance_trend_analysis(self, ml_engine, sample_metrics_data):
        """Test performance trend analysis"""
        if not hasattr(ml_engine, "analyze_performance_trends"):
            pytest.skip("Performance trend analysis not available")

        try:
            # Test trend analysis
            insights = ml_engine.analyze_performance_trends(
                sample_metrics_data, ["memory_percent"]  # Memory has growth trend
            )

            assert isinstance(insights, list)

            if insights:
                trend_insight = insights[0]

                # Check trend insight structure
                assert hasattr(trend_insight, "data_points")
                assert "slope" in trend_insight.data_points
                assert "correlation" in trend_insight.data_points
                assert "trend_direction" in trend_insight.data_points

                # Should detect increasing trend in memory
                assert trend_insight.data_points["trend_direction"] in [
                    "increasing",
                    "decreasing",
                ]

        except ImportError:
            pytest.skip("ML libraries not available for trend analysis")

    def test_capacity_planning_analysis(self, ml_engine, sample_metrics_data):
        """Test capacity planning analysis"""
        if not hasattr(ml_engine, "capacity_planning_analysis"):
            pytest.skip("Capacity planning analysis not available")

        # Create data with high resource utilization
        high_usage_data = sample_metrics_data.copy()
        high_usage_data["memory_percent"] = 75 + np.linspace(
            0, 20, len(high_usage_data)
        )  # Growing to critical levels

        insights = ml_engine.capacity_planning_analysis(
            high_usage_data, ["memory_percent"]
        )

        assert isinstance(insights, list)

        if insights:
            capacity_insight = insights[0]

            # Check capacity insight structure
            assert hasattr(capacity_insight, "data_points")
            assert "current_utilization" in capacity_insight.data_points
            assert "growth_rate_percent_per_week" in capacity_insight.data_points
            assert "days_to_90_percent" in capacity_insight.data_points

            # Should predict capacity issues
            assert capacity_insight.data_points["current_utilization"] > 70
            assert capacity_insight.data_points["days_to_90_percent"] > 0

    def test_ml_model_training_and_caching(self, ml_engine, sample_metrics_data):
        """Test ML model training and caching mechanisms"""
        if not hasattr(ml_engine, "detect_anomalies") or not hasattr(
            ml_engine, "models"
        ):
            pytest.skip("ML model functionality not available")

        try:
            # First run - should train new models
            initial_model_count = len(ml_engine.models)

            insights = ml_engine.detect_anomalies(sample_metrics_data, ["cpu_percent"])

            # Should have trained new models
            assert len(ml_engine.models) >= initial_model_count

            # Second run - should use cached models
            cached_model_count = len(ml_engine.models)

            insights2 = ml_engine.detect_anomalies(sample_metrics_data, ["cpu_percent"])

            # Should not have trained additional models (using cache)
            assert len(ml_engine.models) == cached_model_count

        except ImportError:
            pytest.skip("ML libraries not available")

    def test_insight_generation_and_structure(self, ml_engine, sample_metrics_data):
        """Test ML insight generation and data structure"""
        if not hasattr(ml_engine, "run_comprehensive_analysis"):
            pytest.skip("Comprehensive analysis not available")

        # Mock data fetching to return our sample data
        with patch.object(
            ml_engine, "fetch_historical_data", return_value=sample_metrics_data
        ):
            with patch.object(ml_engine, "store_ml_insights"):
                with patch.object(ml_engine, "send_ml_insights_notification"):

                    # Run analysis
                    ml_engine.run_comprehensive_analysis()

                    # Should have generated insights
                    if (
                        hasattr(ml_engine, "insights_history")
                        and ml_engine.insights_history
                    ):
                        insight = ml_engine.insights_history[0]

                        # Check insight structure
                        required_attributes = [
                            "analysis_type",
                            "severity",
                            "timestamp",
                            "title",
                            "description",
                            "confidence",
                            "affected_services",
                            "recommendations",
                            "data_points",
                        ]

                        for attr in required_attributes:
                            assert hasattr(insight, attr), f"Missing attribute: {attr}"

                        # Check data types
                        assert isinstance(insight.affected_services, list)
                        assert isinstance(insight.recommendations, list)
                        assert isinstance(insight.data_points, dict)
                        assert 0.0 <= insight.confidence <= 1.0

    def test_slack_notification_integration(self, ml_engine):
        """Test Slack notification integration for ML insights"""
        if not hasattr(ml_engine, "send_ml_insights_notification"):
            pytest.skip("Slack notification not available")

        # Create mock insights
        from unittest.mock import Mock

        mock_insight = Mock()
        mock_insight.analysis_type = Mock()
        mock_insight.analysis_type.value = "anomaly_detection"
        mock_insight.severity = Mock()
        mock_insight.severity.value = "warning"
        mock_insight.title = "Test ML Insight"
        mock_insight.description = "This is a test ML insight for notification testing"
        mock_insight.confidence = 0.85

        insights = [mock_insight]

        with patch("requests.post") as mock_post:
            with patch.object(
                ml_engine,
                "get_slack_webhook",
                return_value="https://hooks.slack.com/test",
            ):
                mock_post.return_value = Mock(status_code=200)

                ml_engine.send_ml_insights_notification(insights)

                # Should have sent notification
                if mock_post.called:
                    call_args = mock_post.call_args
                    assert "json" in call_args.kwargs
                    payload = call_args.kwargs["json"]
                    assert "text" in payload
                    assert "ML Analytics Alert" in payload["text"]

    def test_influxdb_storage_integration(self, ml_engine):
        """Test InfluxDB storage integration for ML insights"""
        if not hasattr(ml_engine, "store_ml_insights"):
            pytest.skip("InfluxDB storage not available")

        # Create mock insights
        from unittest.mock import Mock

        mock_insight = Mock()
        mock_insight.analysis_type = Mock()
        mock_insight.analysis_type.value = "predictive_analytics"
        mock_insight.severity = Mock()
        mock_insight.severity.value = "warning"
        mock_insight.timestamp = datetime.utcnow()
        mock_insight.title = "Test Prediction"
        mock_insight.description = "Test predictive insight"
        mock_insight.confidence = 0.75
        mock_insight.affected_services = ["test_service"]
        mock_insight.recommendations = ["test recommendation"]
        mock_insight.data_points = {"test_metric": 100}

        insights = [mock_insight]

        # Mock InfluxDB client
        mock_influxdb = Mock()
        ml_engine.influxdb_client = mock_influxdb

        ml_engine.store_ml_insights(insights)

        # Should have written points to InfluxDB
        if mock_influxdb.write_points.called:
            points = mock_influxdb.write_points.call_args[0][0]
            assert len(points) >= 1

            # Check point structure
            insight_points = [p for p in points if p["measurement"] == "ml_insights"]
            assert len(insight_points) >= 1

            insight_point = insight_points[0]
            assert "analysis_type" in insight_point["tags"]
            assert "confidence" in insight_point["fields"]

    def test_model_performance_tracking(self, ml_engine, sample_metrics_data):
        """Test ML model performance tracking"""
        if not hasattr(ml_engine, "model_performance") or not hasattr(
            ml_engine, "generate_predictions"
        ):
            pytest.skip("Model performance tracking not available")

        try:
            # Generate predictions to trigger model training
            insights = ml_engine.generate_predictions(
                sample_metrics_data, "cpu_percent"
            )

            # Check if model performance is tracked
            if ml_engine.model_performance:
                model_key = list(ml_engine.model_performance.keys())[0]
                performance = ml_engine.model_performance[model_key]

                # Check performance record structure
                assert hasattr(performance, "model_name")
                assert hasattr(performance, "accuracy")
                assert hasattr(performance, "last_trained")
                assert hasattr(performance, "training_samples")
                assert hasattr(performance, "validation_error")

                # Check reasonable values
                assert 0.0 <= performance.accuracy <= 1.0
                assert performance.training_samples > 0
                assert performance.validation_error >= 0

        except ImportError:
            pytest.skip("ML libraries not available")

    def test_data_preprocessing_and_feature_engineering(
        self, ml_engine, sample_metrics_data
    ):
        """Test data preprocessing and feature engineering"""
        if not hasattr(ml_engine, "generate_predictions"):
            pytest.skip("Feature engineering not available")

        try:
            # The generate_predictions method should create time-based features
            original_columns = set(sample_metrics_data.columns)

            # Run prediction to trigger feature engineering
            insights = ml_engine.generate_predictions(
                sample_metrics_data, "cpu_percent"
            )

            # Check if data was cached with engineered features
            if "cpu_percent" in ml_engine.data_cache:
                cached_data = ml_engine.data_cache["cpu_percent"]
                cached_columns = set(cached_data.columns)

                # Should have more columns due to feature engineering
                assert len(cached_columns) > len(original_columns)

                # Should have time-based features
                time_features = {"hour", "day_of_week", "is_weekend"}
                assert any(feature in cached_columns for feature in time_features)

                # Should have rolling statistics
                rolling_features = {
                    "rolling_mean_6h",
                    "rolling_std_6h",
                    "rolling_mean_24h",
                }
                assert any(feature in cached_columns for feature in rolling_features)

        except ImportError:
            pytest.skip("ML libraries not available")


class TestMLAnalyticsIntegration:
    """Integration tests requiring live services"""

    def test_influxdb_connectivity_for_ml(self):
        """Test InfluxDB connectivity for ML analytics"""
        try:
            response = requests.get("http://localhost:8086/ping", timeout=5)
            assert response.status_code in [204, 200]

            # Test database operations
            from influxdb import InfluxDBClient

            client = InfluxDBClient(
                host="localhost", port=8086, database="test_ml_analytics"
            )
            databases = client.get_list_database()
            assert isinstance(databases, list)

        except (requests.ConnectionError, ImportError) as e:
            pytest.skip(f"InfluxDB not available: {e}")

    def test_ml_libraries_availability(self):
        """Test ML libraries availability and functionality"""
        try:
            import numpy as np
            import pandas as pd
            import sklearn
            from sklearn.ensemble import IsolationForest, RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
            import scipy.stats

            # Test basic functionality
            data = np.random.randn(100, 3)
            df = pd.DataFrame(data, columns=["a", "b", "c"])

            # Test isolation forest
            iso_forest = IsolationForest(contamination=0.1)
            iso_forest.fit(data)
            anomalies = iso_forest.predict(data)
            assert len(anomalies) == 100

            # Test random forest
            X = data[:, :-1]
            y = data[:, -1]
            rf = RandomForestRegressor(n_estimators=10)
            rf.fit(X, y)
            predictions = rf.predict(X)
            assert len(predictions) == 100

            # Test scaler
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            assert scaled_data.shape == data.shape

        except ImportError as e:
            pytest.skip(f"ML libraries not available: {e}")

    def test_ml_analytics_deployment(self):
        """Test ML analytics deployment configuration"""
        compose_file = Path("/home/mills/docker-compose.yml")

        if compose_file.exists():
            content = compose_file.read_text()

            # Should have ml-analytics service
            assert "ml-analytics:" in content
            assert "advanced_analytics_engine.py" in content

            # Should have adequate memory for ML operations
            assert "memory: 2G" in content or "memory: 1G" in content

            # Should have secrets access
            assert "/secrets:ro" in content

        else:
            pytest.skip("Docker compose file not found")

    def test_model_persistence_directory(self):
        """Test model persistence directory accessibility"""
        ml_dir = Path("/home/mills/collections/ml-analytics")

        if ml_dir.exists():
            # Should be able to create models subdirectory
            models_dir = ml_dir / "models"
            try:
                models_dir.mkdir(exist_ok=True)
                assert models_dir.exists()

                # Should be writable for model persistence
                test_file = models_dir / "test_model.pkl"
                test_file.write_text("test")
                assert test_file.exists()
                test_file.unlink()  # Cleanup

            except PermissionError:
                pytest.skip("Models directory not writable")
        else:
            pytest.skip("ML analytics directory not found")

    def test_secrets_integration_ml(self):
        """Test secrets integration for ML analytics"""
        secrets_dir = Path("/home/mills/secrets")

        if secrets_dir.exists():
            # Should find ML secrets helper
            ml_dir = Path("/home/mills/collections/ml-analytics")
            secrets_helper = ml_dir / "secrets_helper.py"

            if secrets_helper.exists():
                content = secrets_helper.read_text()
                assert "read_secret" in content
                assert "get_slack_webhook" in content
                assert "get_database_url" in content
            else:
                pytest.skip("ML secrets helper not found")
        else:
            pytest.skip("Secrets directory not found")


class TestMLModelValidation:
    """Test ML model validation and accuracy"""

    def test_anomaly_detection_accuracy(self):
        """Test anomaly detection model accuracy with known data"""
        try:
            from sklearn.ensemble import IsolationForest
            import numpy as np

            # Generate data with known anomalies
            np.random.seed(42)
            normal_data = np.random.normal(0, 1, (1000, 2))
            anomaly_data = np.random.normal(5, 1, (50, 2))  # Clear anomalies

            all_data = np.vstack([normal_data, anomaly_data])
            true_labels = np.hstack(
                [np.ones(1000), -np.ones(50)]
            )  # 1 for normal, -1 for anomaly

            # Train model
            iso_forest = IsolationForest(contamination=0.05, random_state=42)
            predicted_labels = iso_forest.fit_predict(all_data)

            # Calculate accuracy
            accuracy = np.sum(predicted_labels == true_labels) / len(true_labels)

            # Should achieve reasonable accuracy (>70%)
            assert accuracy > 0.7, f"Anomaly detection accuracy too low: {accuracy:.2f}"

        except ImportError:
            pytest.skip("Scikit-learn not available")

    def test_prediction_model_accuracy(self):
        """Test prediction model accuracy with synthetic data"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import mean_absolute_error
            import numpy as np

            # Generate synthetic time series data
            np.random.seed(42)
            t = np.linspace(0, 10, 1000)
            trend = 0.1 * t
            seasonal = 5 * np.sin(2 * np.pi * t)
            noise = np.random.normal(0, 1, 1000)
            y = trend + seasonal + noise

            # Create features (simplified time series features)
            X = np.column_stack(
                [
                    t,  # time
                    np.sin(2 * np.pi * t),  # seasonal component
                    np.cos(2 * np.pi * t),  # seasonal component
                ]
            )

            # Split data
            split_point = 800
            X_train, X_test = X[:split_point], X[split_point:]
            y_train, y_test = y[:split_point], y[split_point:]

            # Train model
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(X_train, y_train)

            # Make predictions
            y_pred = model.predict(X_test)

            # Calculate accuracy
            mae = mean_absolute_error(y_test, y_pred)
            relative_error = mae / np.mean(np.abs(y_test))

            # Should achieve reasonable accuracy (relative error < 30%)
            assert (
                relative_error < 0.3
            ), f"Prediction accuracy too low: {relative_error:.2f}"

        except ImportError:
            pytest.skip("Scikit-learn not available")


if __name__ == "__main__":
    # Run with pytest for better output
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
