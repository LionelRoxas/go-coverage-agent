package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestQuartileOutliers_EmptyInput(t *testing.T) {
	var data Float64Data
	_, err := QuartileOutliers(data)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestQuartileOutliers_NoOutliers(t *testing.T) {
	data := Float64Data{5, 5, 5, 5, 5}
	out, err := QuartileOutliers(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(out.Mild) != 0 || len(out.Extreme) != 0 {
		t.Fatalf("expected no outliers, got mild=%v extreme=%v", out.Mild, out.Extreme)
	}
	// ensure original data unchanged (QuartileOutliers should not modify input)
	expected := Float64Data{5, 5, 5, 5, 5}
	if !reflect.DeepEqual(data, expected) {
		t.Fatalf("input data was modified: got %v want %v", data, expected)
	}
}

func TestQuartileOutliers_MildOutlier(t *testing.T) {
	// dataset where 20 is a mild outlier (beyond inner fence but within outer fence)
	data := Float64Data{1, 2, 3, 4, 5, 6, 7, 8, 9, 20}
	out, err := QuartileOutliers(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(out.Extreme) != 0 {
		t.Fatalf("expected no extreme outliers, got %v", out.Extreme)
	}
	if len(out.Mild) != 1 || out.Mild[0] != 20 {
		t.Fatalf("expected mild outlier 20, got %v", out.Mild)
	}
	// original slice should stay in original order
	expected := Float64Data{1, 2, 3, 4, 5, 6, 7, 8, 9, 20}
	if !reflect.DeepEqual(data, expected) {
		t.Fatalf("input data was modified: got %v want %v", data, expected)
	}
}

func TestQuartileOutliers_ExtremeOutlierAndCopy(t *testing.T) {
	// dataset where 30 is an extreme outlier; also test that the function works on unsorted input
	data := Float64Data{30, 10, 10, 10, 10, 10, 10, 10, 10, 10}
	out, err := QuartileOutliers(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(out.Mild) != 0 {
		t.Fatalf("expected no mild outliers, got %v", out.Mild)
	}
	if len(out.Extreme) != 1 || out.Extreme[0] != 30 {
		t.Fatalf("expected extreme outlier 30, got %v", out.Extreme)
	}
	// Verify original slice order unchanged, confirming a copy was sorted internally
	expected := Float64Data{30, 10, 10, 10, 10, 10, 10, 10, 10, 10}
	if !reflect.DeepEqual(data, expected) {
		t.Fatalf("input data was modified: got %v want %v", data, expected)
	}
}
